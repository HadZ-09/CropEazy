from datetime import datetime
from typing import Any, Dict, List, Optional

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

SEASONS = {
    "Kharif": {"months": [6, 7, 8, 9, 10], "label": "Monsoon / Kharif (Jun–Oct)"},
    "Rabi": {"months": [11, 12, 1, 2, 3], "label": "Winter / Rabi (Nov–Mar)"},
    "Zaid": {"months": [4, 5], "label": "Summer / Zaid (Apr–May)"},
}

PEST_CALENDAR: Dict[str, List[Dict[str, Any]]] = {
    "rice": [
        {"season": "Kharif", "months": ["June", "July", "August"], "pest": "Brown Planthopper", "risk": "High", "advisory": "Monitor paddy fields after transplanting; avoid excessive nitrogen."},
        {"season": "Kharif", "months": ["August", "September"], "pest": "Rice Stem Borer", "risk": "High", "advisory": "Install pheromone traps and remove affected tillers early."},
        {"season": "Kharif", "months": ["September", "October"], "pest": "Leaf Folder", "risk": "Medium", "advisory": "Spray neem-based pesticides when leaf folding is visible."},
        {"season": "Rabi", "months": ["November", "December"], "pest": "Gall Midge", "risk": "Medium", "advisory": "Use resistant varieties in late-sown nurseries."},
    ],
    "wheat": [
        {"season": "Rabi", "months": ["November", "December"], "pest": "Aphids", "risk": "Medium", "advisory": "Inspect crop canopy during tillering stage."},
        {"season": "Rabi", "months": ["January", "February"], "pest": "Termites", "risk": "High", "advisory": "Treat seeds and ensure adequate soil moisture."},
        {"season": "Rabi", "months": ["February", "March"], "pest": "Rust (Yellow/Brown)", "risk": "High", "advisory": "Apply fungicide at first sign of pustules on leaves."},
    ],
    "maize": [
        {"season": "Kharif", "months": ["June", "July"], "pest": "Fall Armyworm", "risk": "High", "advisory": "Scout whorl leaves weekly and apply bio-pesticides early."},
        {"season": "Kharif", "months": ["August", "September"], "pest": "Stem Borer", "risk": "High", "advisory": "Destroy crop residues after harvest to break pest cycle."},
        {"season": "Rabi", "months": ["November", "December"], "pest": "Shoot Fly", "risk": "Medium", "advisory": "Treat seeds before sowing in rabi maize."},
    ],
    "cotton": [
        {"season": "Kharif", "months": ["June", "July", "August"], "pest": "Jassids & Whitefly", "risk": "High", "advisory": "Use yellow sticky traps and avoid broad-spectrum sprays."},
        {"season": "Kharif", "months": ["September", "October"], "pest": "Bollworm", "risk": "High", "advisory": "Release egg parasitoids and monitor boll damage."},
        {"season": "Kharif", "months": ["August", "September"], "pest": "Pink Bollworm", "risk": "Medium", "advisory": "Destroy uprooted stalks immediately after picking."},
    ],
    "potato": [
        {"season": "Rabi", "months": ["December", "January"], "pest": "Aphids", "risk": "Medium", "advisory": "Control aphids to reduce virus spread in seed plots."},
        {"season": "Rabi", "months": ["January", "February"], "pest": "Late Blight", "risk": "High", "advisory": "Spray fungicide before humid weather spells."},
        {"season": "Zaid", "months": ["March", "April"], "pest": "Cutworm", "risk": "Medium", "advisory": "Apply light traps in nursery beds at night."},
    ],
    "chickpea": [
        {"season": "Rabi", "months": ["December", "January"], "pest": "Pod Borer", "risk": "High", "advisory": "Install bird perches and use pheromone traps."},
        {"season": "Rabi", "months": ["February", "March"], "pest": "Wilt", "risk": "Medium", "advisory": "Use wilt-resistant varieties and crop rotation."},
    ],
    "mango": [
        {"season": "Zaid", "months": ["March", "April"], "pest": "Mango Hopper", "risk": "High", "advisory": "Spray during flowering if hopper count exceeds threshold."},
        {"season": "Kharif", "months": ["June", "July"], "pest": "Fruit Fly", "risk": "High", "advisory": "Use bait traps and collect fallen fruits."},
        {"season": "Kharif", "months": ["August"], "pest": "Powdery Mildew", "risk": "Medium", "advisory": "Prune dense branches to improve airflow."},
    ],
    "banana": [
        {"season": "Kharif", "months": ["June", "July", "August"], "pest": "Sigatoka Leaf Spot", "risk": "High", "advisory": "Remove infected leaves and improve drainage."},
        {"season": "Kharif", "months": ["September", "October"], "pest": "Banana Weevil", "risk": "Medium", "advisory": "Use clean planting material and trap adults."},
    ],
    "grapes": [
        {"season": "Rabi", "months": ["December", "January"], "pest": "Thrips", "risk": "Medium", "advisory": "Monitor new shoots during pruning recovery."},
        {"season": "Zaid", "months": ["March", "April"], "pest": "Downy Mildew", "risk": "High", "advisory": "Apply protective sprays before rainfall."},
        {"season": "Kharif", "months": ["July", "August"], "pest": "Mealybug", "risk": "Medium", "advisory": "Release biocontrol agents in infested blocks."},
    ],
    "default": [
        {"season": "Kharif", "months": ["June", "July", "August"], "pest": "General sucking pests", "risk": "Medium", "advisory": "Inspect leaves weekly during monsoon."},
        {"season": "Rabi", "months": ["November", "December", "January"], "pest": "Soil-borne pests", "risk": "Medium", "advisory": "Treat seeds and maintain field hygiene."},
        {"season": "Zaid", "months": ["April", "May"], "pest": "Heat-stress pests", "risk": "Low", "advisory": "Irrigate during peak afternoon heat."},
    ],
}


def normalize_crop_name(crop: str) -> str:
    normalized = (crop or "").lower().strip()
    aliases = {
        "rice, paddy": "rice",
        "paddy": "rice",
        "potatoes": "potato",
        "tomatoes": "tomato",
        "corn": "maize",
        "chana": "chickpea",
    }
    for alias, target in aliases.items():
        if alias in normalized:
            return target
    for key in PEST_CALENDAR:
        if key in normalized:
            return key
    return normalized.split(",")[0].strip() or "default"


def get_pest_prediction(crop: str) -> Dict[str, Any]:
    crop_key = normalize_crop_name(crop)
    entries = PEST_CALENDAR.get(crop_key, PEST_CALENDAR["default"])
    current_month = MONTHS[datetime.now().month - 1]

    current_risks = [
        entry for entry in entries if current_month in entry["months"]
    ]
    if not current_risks:
        current_risks = entries[:2]

    return {
        "crop": crop_key,
        "current_month": current_month,
        "current_season": _season_for_month(datetime.now().month),
        "current_risks": current_risks,
        "seasonal_calendar": entries,
    }


def _season_for_month(month_number: int) -> str:
    for season, meta in SEASONS.items():
        if month_number in meta["months"]:
            return meta["label"]
    return "All seasons"
