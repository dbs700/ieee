# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.2'
#       jupytext_version: 1.0.5
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
import os
import gc
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from datetime import timedelta

from lightgbm import LGBMClassifier
from sklearn.feature_selection import SelectFromModel
from sklearn.pipeline import make_pipeline
import optuna

from codes.utils import cross_val_score_auc, PrunedCV, seed_everything, Reporter

# %%
SEARCH_PARAMS = False
N_FOLD = 6
BOOSTING = 'gbdt'
RANDOM_STATE = 42
START_DATE = datetime.strptime('2017-11-30', '%Y-%m-%d')
seed_everything(RANDOM_STATE)


# %%
y_train = joblib.load('y_train.pkl')
X_train = joblib.load('features_train.pkl')
X_test = joblib.load('features_test.pkl')
sample_submission = pd.read_csv('../input/sample_submission.csv', index_col=0)
group_split = X_train.DT_M

# %%
# train_df = joblib.load('train.pkl')[['TransactionDT']]
# train_df['DT_M'] = train_df['TransactionDT'].apply(lambda x: (START_DATE + timedelta(seconds = x)))
# train_df['DT_M'] = (train_df['DT_M'].dt.year-2017)*12 + train_df['DT_M'].dt.month 
# train_df = train_df[train_df['DT_M']<(train_df['DT_M'].max())]

# X_train['DT_M'] = train_df['DT_M']
# X_train['DT_M'].fillna(17, inplace=True)

# %%
seed_everything(RANDOM_STATE)
y_sampled = pd.concat([y_train[y_train == 1], y_train[y_train == 0].sample(frac=0.2)])
X_train_sampled = X_train.loc[y_sampled.index, :]
group_split_sampled = X_train_sampled.DT_M
X_train_sampled.drop('DT_M', axis=1, inplace=True)
X_train.drop('DT_M', axis=1, inplace=True)

# %% [markdown]
# ### Model and training

# %%
model = LGBMClassifier(metric='auc', boosting_type=BOOSTING)
prun = PrunedCV(N_FOLD, 0.02, splits_to_start_pruning=3, minimize=False)


# %%
def objective(trial):
    
    joblib.dump(study, 'study_{}.pkl'.format(BOOSTING)) 

    
    params = {
        'num_leaves': trial.suggest_int('num_leaves', 10, 1500), 
        'max_depth': trial.suggest_int('max_depth', 10, 1000), 
        'subsample_for_bin': trial.suggest_int('subsample_for_bin', 1000, 5000000), 
        'min_child_samples': trial.suggest_int('min_child_samples', 200, 100000), 
        'reg_alpha': trial.suggest_loguniform('reg_alpha', 0.00000000001, 10.0),
        'colsample_bytree': trial.suggest_loguniform('colsample_bytree', 0.0001, 1.0),
        'learning_rate': trial.suggest_loguniform('learning_rate', 0.00001, 2.0),
        'n_estimators': trial.suggest_int('n_estimators', 500, 2000)
    }
    
    model.set_params(**params)
        
    return prun.cross_val_score(model, 
                                X_train_sampled, 
                                y_sampled, 
                                split_type='groupkfold',
                                groups=group_split_sampled,
                                metric='auc',
                                random_state=RANDOM_STATE)

# %%
if SEARCH_PARAMS:
    if os.path.isfile('study_{}.pkl'.format(BOOSTING)):
        study = joblib.load('study_{}.pkl'.format(BOOSTING))
    else:
        study = optuna.create_study()

    study.optimize(objective, timeout=60 * 60 * 21)
    joblib.dump(study, 'study_{}.pkl'.format(BOOSTING))
    best_params = study.best_params

else:

    best_params = {'num_leaves': 302,
                     'max_depth': 157,
                     'n_estimators': 1200,
                     'subsample_for_bin': 290858,
                     'min_child_samples': 79,
                     'reg_alpha': 0.9919573524807885,
                     'colsample_bytree': 0.5653288564015742,
                     'learning_rate': 0.028565794309535042}

# %%
model.set_params(**best_params)

# %%
seed_everything(RANDOM_STATE)
cross_val_score_auc(model,
                    X_train_sampled,
                    y_sampled,
                    n_fold=N_FOLD,
                    random_state=RANDOM_STATE,
                    predict=True,
                    X_test=X_test,
                    shuffle=True,
                    split_type='stratifiedkfold',
                    groups=group_split_sampled,
                    submission=sample_submission)

# %%
