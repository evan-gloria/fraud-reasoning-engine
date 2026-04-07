"""
graph_skill.py

A tool that allows the Agent to render bar charts using Matplotlib.
It saves the file locally and returns a special tag to the Agent to output to Streamlit.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path

# Ensure the app folder exists to store the image
OUTPUT_DIR = Path(__file__).parent.parent / "app" / "static"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_chart(chart_type: str, title: str, x_labels: list[str], y_values: list[float]) -> str:
    """
    Renders a chart dynamically based on chart_type and saves it as a PNG file.
    
    Args:
        chart_type: The type of chart ('bar', 'line', 'scatter', 'pie').
        title: The title of the chart.
        x_labels: The labels for the X-axis (e.g., categories).
        y_values: The values for the Y-axis.
    """
    try:
        plt.clf()
        sns.set_theme(style="whitegrid", context="talk", palette="deep")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        chart_type = chart_type.lower().strip()
        
        if chart_type == "bar":
            sns.barplot(x=x_labels, y=y_values, ax=ax, hue=x_labels, legend=False)
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "line":
            sns.lineplot(x=x_labels, y=y_values, ax=ax, marker="o", linewidth=2.5)
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "scatter":
            sns.scatterplot(x=x_labels, y=y_values, ax=ax, s=100)
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "pie":
            # Pie charts don't leverage seaborn directly as well, fallback to plt
            plt.pie(y_values, labels=x_labels, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("deep"))
        else:
            return f"Error: Unknown chart_type '{chart_type}'. Supported types: bar, line, scatter, pie."
            
        plt.title(title, fontsize=18, pad=20, fontweight='bold')
        if chart_type != "pie":
            plt.ylabel("Value", fontsize=14)
            plt.xlabel("Categories", fontsize=14)
            
        plt.tight_layout()
        
        # Save to file
        filename = "latest_chart.png"
        filepath = OUTPUT_DIR / filename
        plt.savefig(filepath, dpi=150)
        plt.close()
        
        return f"Chart successfully generated and saved. You MUST tell the user 'Here is the chart:' and then output exactly this tag on a new line: <CHART>{filename}</CHART>"
        
    except Exception as e:
        return f"Error plotting the chart: {str(e)}"
