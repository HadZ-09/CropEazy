"""
Crop Recommendation - Prediction Script
----------------------------------------
Loads the trained RandomForestClassifier ('crop_recommendation_model.pkl')
produced by the training notebook and predicts the recommended crop given
soil and climate parameters: N, P, K, temperature, humidity, ph, rainfall.

Usage:
    # 1) Command-line arguments
    python predict.py --N 90 --P 42 --K 43 --temperature 20.87 \
        --humidity 82.0 --ph 6.5 --rainfall 202.9

    # 2) Interactive mode (no arguments passed)
    python predict.py

    # 3) Import and use as a function in your own code
    from predict import predict_crop
    predict_crop(90, 42, 43, 20.87, 82.0, 6.5, 202.9)
"""

import argparse
import sys
import joblib
import pandas as pd

MODEL_PATH = "crop_recommendation_model.pkl"
FEATURE_NAMES = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]


def load_model(model_path: str = MODEL_PATH):
    """Load the trained model from disk."""
    try:
        model = joblib.load(model_path)
        return model
    except FileNotFoundError:
        sys.exit(
            f"Error: could not find '{model_path}'.\n"
            "Make sure you've run the training notebook first so that "
            f"'{model_path}' exists in this directory, or pass the correct "
            "path via --model."
        )


def predict_crop(N, P, K, temperature, humidity, ph, rainfall,
                  model_path: str = MODEL_PATH, top_n: int = 3):
    """
    Predict the recommended crop for a single set of input parameters.

    Returns:
        dict with the top prediction and (if supported) top_n probabilities.
    """
    model = load_model(model_path)

    input_df = pd.DataFrame(
        [[N, P, K, temperature, humidity, ph, rainfall]],
        columns=FEATURE_NAMES,
    )

    prediction = model.predict(input_df)[0]
    result = {"recommended_crop": prediction}

    # If the model supports probabilities (RandomForestClassifier does),
    # show the top-N most likely crops for extra context.
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(input_df)[0]
        classes = model.classes_
        ranked = sorted(zip(classes, proba), key=lambda x: x[1], reverse=True)
        result["top_predictions"] = ranked[:top_n]

    return result


def print_result(result: dict):
    print("\n=== Crop Recommendation Result ===")
    print(f"Recommended crop: {result['recommended_crop']}")
    if "top_predictions" in result:
        print("\nTop candidates (crop : confidence):")
        for crop, prob in result["top_predictions"]:
            print(f"  {crop:15s} : {prob * 100:.2f}%")
    print("===================================\n")


def get_float(prompt: str) -> float:
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Please enter a valid number.")


def interactive_mode(model_path: str):
    print("Enter the following values to get a crop recommendation:\n")
    N = get_float("Nitrogen (N): ")
    P = get_float("Phosphorus (P): ")
    K = get_float("Potassium (K): ")
    temperature = get_float("Temperature (°C): ")
    humidity = get_float("Humidity (%): ")
    ph = get_float("Soil pH: ")
    rainfall = get_float("Rainfall (mm): ")

    result = predict_crop(N, P, K, temperature, humidity, ph, rainfall,
                           model_path=model_path)
    print_result(result)


def main():
    parser = argparse.ArgumentParser(
        description="Predict the recommended crop from soil/climate parameters."
    )
    parser.add_argument("--N", type=float, help="Nitrogen content")
    parser.add_argument("--P", type=float, help="Phosphorus content")
    parser.add_argument("--K", type=float, help="Potassium content")
    parser.add_argument("--temperature", type=float, help="Temperature in °C")
    parser.add_argument("--humidity", type=float, help="Relative humidity in %%")
    parser.add_argument("--ph", type=float, help="Soil pH value")
    parser.add_argument("--rainfall", type=float, help="Rainfall in mm")
    parser.add_argument(
        "--model", type=str, default=MODEL_PATH,
        help=f"Path to the trained model file (default: {MODEL_PATH})"
    )

    args = parser.parse_args()
    provided = [args.N, args.P, args.K, args.temperature,
                args.humidity, args.ph, args.rainfall]

    if all(v is not None for v in provided):
        result = predict_crop(
            args.N, args.P, args.K, args.temperature,
            args.humidity, args.ph, args.rainfall,
            model_path=args.model,
        )
        print_result(result)
    elif any(v is not None for v in provided):
        sys.exit(
            "Error: please provide ALL seven parameters via command-line "
            "arguments, or none of them to enter interactive mode."
        )
    else:
        interactive_mode(args.model)


if __name__ == "__main__":
    main()
