from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV, KFold
import logging
from model.time import ARIMAWrapper, SARIMAXWrapper


class ModelManager():
    def __init__(self, models, seed=None, time_column=None):
        self.model_path = 'saved_model/'
        self.seed = seed
        self.time_column = time_column
        self.all_models = {
            'LinearRegression': (LinearRegression(), {}),
            'KNN': (KNeighborsRegressor(), {'n_neighbors': [3, 5, 7, 9]}),
            'SVM': (SVR(), {'C': [0.1, 1, 10]}),
            'DecisionTree': (DecisionTreeRegressor(), {'max_depth': [3, 5, 7, 9]}),
            'RandomForest': (RandomForestRegressor(), {'n_estimators': [50, 100, 200], 'max_depth': [3, 5, 7]}),
            'XGBoost': (XGBRegressor(), {'n_estimators': [50, 100, 200], 'max_depth': [3, 5, 7]}),
            'LightGBM': (LGBMRegressor(verbose=-1), {'n_estimators': [50, 100, 200], 'max_depth': [3, 5, 7]}),
            'MLP': (MLPRegressor(max_iter=1000), {'hidden_layer_sizes': [(50,), (100,), (50, 50)], 'alpha': [0.0001, 0.001, 0.01]})
        }
        # 若有時間欄位，也加使用時間序列模型
        if self.time_column is not None:
            logging.info("加入時間序列模型")
            self.all_models.update({
                'ARIMA': (ARIMAWrapper(order=(1, 1, 1)), {'order': [(1, 1, 1), (2, 1, 2)]}),
                'SARIMA': (SARIMAXWrapper(order=(1, 1, 1), seasonal_order=(1, 1, 1, 12)), {'order': [(1, 1, 1), (2, 1, 2)], 'seasonal_order': [(1, 1, 1, 12), (2, 1, 2, 12)]})
            })

        if models == 'all':
            self.use_models = self.all_models
        else:   
            # 將字串轉換為列表
            if isinstance(models, str):
                models = [model.strip() for model in models.split(',')]
            # 留下使用者選擇的模型
            self.use_models = {k: v for k, v in self.all_models.items() if k in models}


    def cv_fit(self, X, y, n_splits=5):
        cv_results = {}
        self.best_models = {}
        fold_scores = {}
        
        if self.time_column is not None:
            cv = TimeSeriesSplit(n_splits=n_splits)
        else:
            cv = KFold(n_splits=n_splits, shuffle=True, random_state=self.seed)
        
        for name, (model, params) in self.use_models.items():
            if 'random_state' in model.get_params():
                model.set_params(random_state=self.seed)
            logging.info(f"Training model: {name} with params: {params}")
            
            grid_search = GridSearchCV(model, params, cv=cv, scoring='neg_mean_absolute_percentage_error', return_train_score=True)
            grid_search.fit(X, y)
            self.best_models[name] = grid_search.best_estimator_
            cv_results[name] = -grid_search.best_score_ #最好的參數組合的 5 fold 平均MAPE

            # Log the results
            best_estimator = grid_search.best_estimator_
            if name == 'XGBoost': # XGBoost莫名其妙印很多參數出來..
                key_params = {k: v for k, v in best_estimator.get_params().items() if k in ['n_estimators', 'max_depth', 'learning_rate']}
                logging.info(f"Best estimator for {name}: {type(best_estimator).__name__} with params: {key_params}")
            else:
                logging.info(f"Best estimator for {name}: {best_estimator}")
            
            logging.info(f"Cross-validation MAPE for {name}: {cv_results[name]}")


            # Extract fold scores
            fold_scores[name] = -grid_search.cv_results_['split0_test_score'], -grid_search.cv_results_['split1_test_score'], -grid_search.cv_results_['split2_test_score'], -grid_search.cv_results_['split3_test_score'], -grid_search.cv_results_['split4_test_score']

            # Log the fold scores
            # for i, score in enumerate(fold_scores[name]):
            #     logging.info(f"Fold {i + 1} score for {name}: {score}")

        return self.best_models