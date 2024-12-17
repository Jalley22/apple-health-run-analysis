# Run Insights from Apple Health 🚀

Analyze and visualize Apple Health run data for performance insights, including distance, duration, and energy burned metrics.

---

## Overview 📊
This project processes and extracts running workout data from Apple Health's `export.xml` file. It automates data cleaning, transformation, and outputs a clean table (CSV) for further analysis.

---

## Features 🏃‍♂️
- Extract key metrics such as:
  - **Start and End Date**
  - **Run Duration (minutes)**
  - **Distance (km)**
  - **Calories Burned**
- Output clean and structured data to CSV for analysis.
- Provides an example Python script for parsing and analyzing data.

---

## Repository Structure 📁
📂 apple-health-run-analysis │ 
├── data/ 
│ └── export.xml # Sample raw Health data export 
│ ├── scripts/ 
│ └── parse_health_data.py # Python script for processing data 
│ ├── output/ 
│ └── running_data.csv # Cleaned and structured run data 
│ └── README.md # Project documentation


---

## Prerequisites 🔧
- Python 3.x
- Required libraries: `pandas`

Install the dependencies:
```bash
pip install pandas
```
## How to Use 🛠️
Export your Apple Health data:
Open the Health app on your iPhone.
Go to your profile > Export All Health Data.
Place the export.xml file in the data/ folder.

```
python scripts/parse_health_data.py
```
