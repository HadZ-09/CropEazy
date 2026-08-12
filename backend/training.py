import os
from pathlib import Path
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from joblib import dump

from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline 
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.metrics import root_mean_squared_error, mean_absolute_error, r2_score

def prediction():
    try:
        load_dotenv()
        RANDOM_STATE = int(os.getenv("RANDOM_STATE"))
        TEST_SIZE = float(os.getenv("TEST_SIZE"))
        TARGETCOL = os.getenv("TARGETCOL")
        
        PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT")).resolve()
        DATASET_PATH = PROJECT_ROOT / os.getenv("DATASET_DIR") / os.getenv("YIELD_DATASET", "yield_df.csv")
        MODEL_PATH = PROJECT_ROOT / os.getenv("MODEL_DIR") / os.getenv("YIELD_MODEL_NAME", "model.joblib")
        
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        df = pd.read_csv(DATASET_PATH)




        key_check = df.groupby(['Area', 'Item', 'Year'])[
            ['hg/ha_yield', 'average_rain_fall_mm_per_year','pesticides_tonnes']
        ].nunique()
        assert (key_check.max() == 1).all(), "Found a key with more than one value in a supposedly-constant column"

        df = df.groupby(['Area', 'Item', 'Year'], as_index=False).agg({
            'hg/ha_yield': 'first',
            'average_rain_fall_mm_per_year': 'first',
            'pesticides_tonnes': 'first',
            'avg_temp': 'mean'
        })

        print("Collapsed shape:", df.shape)
        assert df.duplicated(subset=['Area', 'Item', 'Year']).sum() == 0



  
        X = df.drop(columns=[TARGETCOL])
        y = df[TARGETCOL]
        
        # Consider changing this to just df["Area"] if you want pure spatial splitting
        groups = df["Area"].astype(str) + "_" + df["Year"].astype(str)




        gss = GroupShuffleSplit(n_splits=1, random_state=RANDOM_STATE, test_size=TEST_SIZE)
        train_idx, test_idx = next(gss.split(X, y, groups=groups))

        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        print("Train shape:", X_train.shape)
        print("Test shape:", X_test.shape)
        print("Group overlap (should be 0):", len(set(groups.iloc[train_idx]) & set(groups.iloc[test_idx])))



    
        num_cols = ["Year", "avg_temp", "average_rain_fall_mm_per_year", "pesticides_tonnes"]
        cat_cols = ["Area", "Item"]
        
        num_preprocess = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler())
        ])

        cat_preprocess = Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("ohc", OneHotEncoder(handle_unknown='ignore', sparse_output=False))
        ])
        
        data_preprocess = ColumnTransformer(transformers=[
            ("num", num_preprocess, num_cols),
            ("cat", cat_preprocess, cat_cols)
        ])
        
        final_model = Pipeline([
            ("data", data_preprocess),
            ("model", RandomForestRegressor(
                n_estimators=300,
                min_samples_split=2,
                min_samples_leaf=2,
                max_features=0.3,
                max_depth=50,
                bootstrap=True,  # Changed to True for standard RF bagging behavior
                random_state=RANDOM_STATE
            ))
        ])


    
        final_model.fit(X_train, y_train)

        train_preds = final_model.predict(X_train)
        test_preds = final_model.predict(X_test)

        print("\n--- Training Performance ---")
        print("MAE Summary:  ", mean_absolute_error(y_train, train_preds))
        print("RMSE Summary: ", root_mean_squared_error(y_train, train_preds))
        print("R2 Score:     ", r2_score(y_train, train_preds))
        print("*" * 50)

        print("--- Testing Performance ---")
        print("MAE Summary:  ", mean_absolute_error(y_test, test_preds))
        print("RMSE Summary: ", root_mean_squared_error(y_test, test_preds))
        print("R2 Score:     ", r2_score(y_test, test_preds))

        #       STEP 6: Save Model
        dump(final_model, MODEL_PATH)
        print(f"\nModel successfully saved to {MODEL_PATH}")
       
    except Exception as e:
        print(f"\n❌ Execution failed!")
        raise e

if __name__ == "__main__":
    prediction()
