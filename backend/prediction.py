import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from joblib import load

def load_trained_model():
    """Loads the trained model pipeline from the path specified in .env"""
    load_dotenv()
    PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", ".")).resolve()
    MODEL_PATH = (
        PROJECT_ROOT
        / os.getenv("MODEL_DIR", "models")
        / os.getenv("YIELD_MODEL_NAME", "model.joblib")
    )
    
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"No model found at {MODEL_PATH}. Please run the training script first!")
        
    print(f"Loading model from: {MODEL_PATH}")
    return load(MODEL_PATH)

def predict_from_csv(input_csv_path, output_csv_path=None):
    """
    Loads new data from a CSV file, makes predictions, and optionally saves them.
    Note: The input CSV columns must match the expected features:
    ['Area', 'Item', 'Year', 'avg_temp', 'average_rain_fall_mm_per_year', 'pesticides_tonnes']
    """
    model = load_trained_model()
    
    print(f"Reading input data from: {input_csv_path}")
    df_new = pd.read_csv(input_csv_path)
    
    # Make predictions using the complete pipeline (handles encoding & scaling automatically)
    predictions = model.predict(df_new)
    df_new["predicted_hg_ha_yield"] = predictions
    
    if output_csv_path:
        pd.DataFrame(df_new).to_csv(output_csv_path, index=False)
        print(f"🚀 Predictions saved successfully to {output_csv_path}")
        
    return df_new

def predict_single_record(data_dict):
    """
    Makes a prediction on a single record passed as a dictionary.
    Example input:
        {
            "Area": "India",
            "Item": "Rice",
            "Year": 2026,
            "avg_temp": 26.5,
            "average_rain_fall_mm_per_year": 1100.0,
            "pesticides_tonnes": 55000.0
        }
    """
    model = load_trained_model()
    df_single = pd.DataFrame([data_dict])
    
    prediction = model.predict(df_single)[0]
    return prediction


if __name__ == "__main__":
    
    sample_data = {
        "Area": "India",
        "Item": "Rice",
        "Year": 2026,
        "avg_temp": 25.4,
        "average_rain_fall_mm_per_year": 1200.0,
        "pesticides_tonnes": 45000.0
    }
    
    print("\n--- Prediction Example ---")
    try:
        predicted_yield = predict_single_record(sample_data)
        print(f"Input: {sample_data['Item']} in {sample_data['Area']} ({sample_data['Year']})")
        print(f"Predicted Yield: {predicted_yield:.2f} hg/ha")
    except Exception as e:
        print(f"Failed to predict: {e}")

    # --- EXAMPLE 2: Predicting on a new batch CSV ---
    # To use this, uncomment the lines below and adjust your file paths:
    # print("\n--- Batch CSV Prediction Example ---")
    # load_dotenv()
    # root = Path(os.getenv("PROJECT_ROOT", ".")).resolve()
    # input_file = root / "data" / "new_unseen_data.csv"
    # output_file = root / "data" / "predictions_output.csv"
    # 
    # if input_file.exists():
    #     predict_from_csv(input_file, output_file)