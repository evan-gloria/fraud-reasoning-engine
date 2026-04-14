"""
graph_skill.py

A tool that allows the Agent to render bar charts using Matplotlib.
It saves the file locally and returns a special tag to the Agent to output to Streamlit.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path

# Ensure the ui folder exists to store the image
OUTPUT_DIR = Path(__file__).parent.parent / "ui" / "static"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_chart(title: str, x_labels: list[str], series: list[dict],
                   x_label: str = "", y_label: str = "") -> str:
    """
    Renders a multi-series chart dynamically and saves it as a PNG file.
    Supports bar, line, scatter, pie, and combo charts with dual Y-axes.
    
    Args:
        title: The title of the chart.
        x_labels: The labels for the X-axis (e.g., categories or dates).
        series: A list of series dictionaries, e.g.:
               [{"label": "Daily", "type": "bar", "data": [1, 2], "secondary_y": False}]
        x_label: Label for the X-axis (e.g., "Date", "Merchant Category").
        y_label: Label for the primary Y-axis (e.g., "Transaction Count", "Amount (AUD)").
    """
    try:
        plt.clf()
        sns.set_theme(style="whitegrid", context="talk", palette="deep")
        
        # Check if this is a pie chart (uses the first series only)
        is_pie = any(s.get("type", "").lower().strip() == "pie" for s in series)
        
        if is_pie:
            fig, ax = plt.subplots(figsize=(10, 8))
            pie_series = next(s for s in series if s.get("type", "").lower().strip() == "pie")
            data = pie_series.get("data", [])
            
            # Universal Sync Guard: Align data and labels
            min_len = min(len(data), len(x_labels))
            plot_data = data[:min_len]
            plot_labels = x_labels[:min_len]
            
            colors = sns.color_palette("deep", len(plot_labels))
            wedges, texts, autotexts = ax.pie(
                plot_data, labels=plot_labels, autopct='%1.1f%%',
                startangle=140, colors=colors, textprops={'fontsize': 12}
            )
            for autotext in autotexts:
                autotext.set_fontweight('bold')
            plt.title(title, fontsize=20, pad=25, fontweight='bold')
        else:
            fig, ax1 = plt.subplots(figsize=(12, 7))
            ax2 = None
            
            # Sync Guard for non-pie charts (ensures X_labels match data points)
            min_x_len = len(x_labels)
            
            # Iterate and plot each series
            for i, s in enumerate(series):
                label = s.get("label", f"Series {i+1}")
                chart_type = s.get("type", "bar").lower().strip()
                data = s.get("data", [])
                use_secondary = s.get("secondary_y", False)
                
                # Selection-level Sync Guard: Ensure data doesn't exceed X labels
                plot_data = data[:min_x_len]
                plot_labels = x_labels[:len(plot_data)]
                
                # Select target axis
                target_ax = ax1
                if use_secondary:
                    if ax2 is None:
                        ax2 = ax1.twinx()
                        ax2.grid(False)
                    target_ax = ax2

                if chart_type == "bar":
                    target_ax.bar(plot_labels, plot_data, label=label, alpha=0.7)
                elif chart_type == "barh":
                    target_ax.barh(plot_labels, plot_data, label=label, alpha=0.7)
                elif chart_type == "line":
                    target_ax.plot(plot_labels, plot_data, label=label, marker="o", linewidth=3)
                elif chart_type == "scatter":
                    target_ax.scatter(plot_labels, plot_data, label=label, s=100)
                else:
                    continue

            # Formatting
            plt.title(title, fontsize=20, pad=25, fontweight='bold')
            # For horizontal bars, swap axis label positions for clarity
            is_horizontal = any(s.get("type", "").lower().strip() == "barh" for s in series)
            if is_horizontal:
                if y_label: ax1.set_xlabel(y_label, fontsize=14)
                if x_label: ax1.set_ylabel(x_label, fontsize=14)
            else:
                if x_label: ax1.set_xlabel(x_label, fontsize=14)
                if y_label: ax1.set_ylabel(y_label, fontsize=14)
                
            if ax2:
                secondary_series = [s for s in series if s.get("secondary_y")]
                if secondary_series:
                    ax2.set_ylabel(secondary_series[0].get("label", ""), fontsize=14)
                
            # Combine legends
            lines, labels = ax1.get_legend_handles_labels()
            if ax2:
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines + lines2, labels + labels2, loc='upper left', frameon=True)
            else:
                ax1.legend(loc='upper left', frameon=True)

            if len(x_labels) > 6:
                ax1.tick_params(axis='x', rotation=45)
                for lbl in ax1.get_xticklabels(): lbl.set_ha('right')
            else:
                ax1.tick_params(axis='x', rotation=0)
            
        plt.tight_layout()
        
        import uuid
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        filepath = OUTPUT_DIR / filename
        plt.savefig(filepath, dpi=150)
        plt.close()
        
        return f"<CHART>{filename}</CHART>"
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"Error plotting the chart: {str(e)}"
