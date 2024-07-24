import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import numpy as np
from sklearn.metrics import cohen_kappa_score
from catboost import CatBoostClassifier
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import f1_score

import warnings
warnings.filterwarnings("ignore")

pd.set_option("display.max_columns", None)
pd.set_option("display.float_format", lambda x: "%.3f" % x)

###########
# READ DATA
###########

df_survey = pd.read_csv("./datasets/mental_final.csv")

###########
# FEATURE EXTRACTION
###########

def create_age_group(age):
    if age >= 10 and age <= 17:
        return "Teenager"
    elif age >= 18 and age <= 25:
        return "Young Adult"
    elif age >= 26 and age <= 35:
        return "Adult"
    elif age >= 36:
        return "Middle Age"

df_survey["age_group"] = df_survey["age"].apply(create_age_group)

##############

df_survey["listening_habit"] = pd.cut(df_survey["hours_per_day"], bins=[0, 2, 4, 7, float("inf")], 
                                      labels=[0, 1, 2, 3])

df_survey["listening_habit"] = df_survey["listening_habit"].astype(int)

##############

col_enc = [col for col in df_survey.columns if "frequency" in col]

# dict
ordinal_mapping = {"Never": 0,
                   "Rarely": 1,
                   "Sometimes": 2,
                   "Often": 3}

for col in col_enc:
    df_survey[f'{col}'] = df_survey[col].apply(lambda x: ordinal_mapping.get(x))
    
df_survey["average_frequency"] = df_survey[col_enc].mean(axis=1)

##############

def calculate_genre_diversity(row):
    non_zero_genres = sum(1 for value in row if value > 0)
    return non_zero_genres / len(col_enc)

df_survey["genre_diversity"] = df_survey[col_enc].apply(calculate_genre_diversity, axis=1)

##############

def get_favorite_genre(row):
    max_value = row.max()
    if max_value == 0:
        return "None"
    max_indices = np.where(row == max_value)[0]
    if len(max_indices) > 1:
        return "Multiple"
    return col_enc[max_indices[0]].replace("frequency", "")

df_survey["top_genre"] = df_survey[col_enc].apply(get_favorite_genre, axis=1)

###########
# ENCODING & SCALING
###########

def grab_col_names(dataframe, cat_th=10, car_th=20):
    # cat_cols, cat_but_car
    cat_cols = [col for col in dataframe.columns if dataframe[col].dtypes == "O"]
    num_but_cat = [col for col in dataframe.columns if dataframe[col].nunique() < cat_th and
                   dataframe[col].dtypes != "O"]
    cat_but_car = [col for col in dataframe.columns if dataframe[col].nunique() > car_th and
                   dataframe[col].dtypes == "O"]
    cat_cols = cat_cols + num_but_cat
    cat_cols = [col for col in cat_cols if col not in cat_but_car]

    # num_cols
    num_cols = [col for col in dataframe.columns if dataframe[col].dtypes != "O"]
    num_cols = [col for col in num_cols if col not in num_but_cat]

    print(f"Observations: {dataframe.shape[0]}")
    print(f"Variables: {dataframe.shape[1]}")
    print(f"cat_cols: {len(cat_cols)}")
    print(f"num_cols: {len(num_cols)}")
    print(f"cat_but_car: {len(cat_but_car)}")
    print(f"num_but_cat: {len(num_but_cat)}")
    
    return cat_cols, num_cols, cat_but_car

cat_cols, num_cols, cat_but_car = grab_col_names(df_survey)

num_cols = [col for col in num_cols if col not in ["anxiety", "depression", "insomnia", "obsession", "tempo"]]

##############

def label_encoder(dataframe, binary_col):
    labelencoder = LabelEncoder()
    dataframe[binary_col] = labelencoder.fit_transform(dataframe[binary_col])
    return dataframe

binary_cols = [col for col in df_survey.columns if df_survey[col].dtypes == "O" and df_survey[col].nunique() == 2]

for col in binary_cols:
    df_survey = label_encoder(df_survey, col)

df_survey["music_effects"] = df_survey["music_effects"].map({"Worsen": 0, "No Effect": 1, "Improve": 2})

df_survey["age_group"] = df_survey["age_group"].map({"Teenager": 0, "Young Adult": 1, "Adult": 2, "Middle Age": 3})

##############

ohe_cols = ["streaming_service", "fav_genre", "top_genre"]

def one_hot_encoder(dataframe, categorical_cols, drop_first=True):
    dataframe = pd.get_dummies(dataframe, columns=categorical_cols, dtype=int, drop_first=drop_first)
    return dataframe

df_survey = one_hot_encoder(df_survey, ohe_cols, drop_first=True)

df_survey.head()

##############

scaler = StandardScaler()
df_survey[num_cols] = scaler.fit_transform(df_survey[num_cols])

##############
##############
##############

###########
# BASE MODEL
###########

y = df_survey["anxiety"]
X = df_survey.drop(columns=["tempo", "anxiety", "depression", "insomnia", "obsession"], axis=1)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
##############

def weighted_kappa(y_true, y_pred):
    return cohen_kappa_score(y_true, np.round(y_pred), weights="quadratic")

model = CatBoostClassifier(iterations=1000,
                           learning_rate=0.05,
                           depth=6,
                           loss_function="MultiClass",
                           eval_metric="WKappa")

model.fit(X_train, y_train,
          eval_set=(X_test, y_test),
          verbose=100)

y_pred = model.predict(X_test)

wkappa_score = weighted_kappa(y_test, y_pred)
print(f"Ağırlıklı Kappa Skoru: {wkappa_score}")

f1score = f1_score(y_test, y_pred, average='weighted')

random_sample = X.sample(1)
prediction = model.predict(random_sample)

def plot_importance(model, features, dataframe, save=False):
    num = len(dataframe)
    feature_imp = pd.DataFrame({"Value": model.feature_importances_, "Feature": features.columns})
    plt.figure(figsize=(10, 10))
    sns.set_theme(font_scale=1)
    sns.barplot(x="Value", y="Feature", data=feature_imp.sort_values(by="Value", ascending=False)[0:num])
    plt.title("Features")
    plt.tight_layout()
    plt.show()
    if save:
        plt.savefig("importances.png")

plot_importance(model, X, df_survey)