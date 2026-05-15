"""
graph_skill.py

A tool that allows the Agent to render bar charts using Matplotlib.
It saves the file locally and returns a special tag to the Agent to output to Streamlit.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import os
from pathlib import Path
from typing import Union

# Ensure the ui folder exists to store the image
OUTPUT_DIR = Path(__file__).parent.parent / "ui" / "static"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Theme presets ────────────────────────────────────────────────────────────
# Maps a theme name to (seaborn_style, fig_facecolor, ax_facecolor, text_color, grid_color)
_THEMES = {
    "whitegrid":      ("whitegrid",   "white",   "white",   "#1a1a2e", "#d0d0d0"),
    "darkgrid":       ("darkgrid",    "#1e1e2e", "#1e1e2e", "#e0e0e0", "#3a3a5a"),
    "dark":           ("dark",        "#121212", "#1e1e1e", "#f0f0f0", "#333333"),
    "minimal":        ("white",       "white",   "white",   "#333333", "#e8e8e8"),
    "corporate_dark": ("dark",        "#0f1923", "#162030", "#e8eaf6", "#263244"),
}

# ─── Named palette shortcuts (these resolve to seaborn or matplotlib palettes) ─
_NAMED_PALETTES = {
    "deep", "muted", "pastel", "bright", "dark", "colorblind",
    "viridis", "plasma", "rocket", "mako", "flare", "crest", "magma",
    "Blues", "Greens", "Reds", "Purples", "Oranges",
    "Set1", "Set2", "Set3", "tab10", "tab20",
}

def generate_chart(
    title: str,
    x_labels: list[str],
    series: list[dict],
    x_label: str = "",
    y_label: str = "",
    color_palette: Union[str, list] = "deep",
    theme: str = "whitegrid",
    show_data_labels: bool = False,
    bar_width: float = 0.7,
) -> str:
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
        color_palette: Named palette string (e.g. "deep", "rocket", "viridis", "muted",
                       "corporate_dark") OR a list of hex colour strings
                       (e.g. ["#4e79a7", "#f28e2b"]). Defaults to "deep".
        theme: Overall figure style. One of: "whitegrid" (default), "darkgrid",
               "dark", "minimal", "corporate_dark".
        show_data_labels: If True, annotate each data point with its value.
        bar_width: Width of bar chart bars (0.1 – 1.0). Defaults to 0.7.
    """
    try:
        plt.clf()

        # ── Resolve theme ────────────────────────────────────────────────────
        theme_key = theme.lower().strip() if isinstance(theme, str) else "whitegrid"
        sns_style, fig_bg, ax_bg, text_color, grid_color = _THEMES.get(
            theme_key, _THEMES["whitegrid"]
        )
        sns.set_theme(style=sns_style, context="talk")

        # ── Resolve colour palette ────────────────────────────────────────────
        if isinstance(color_palette, list):
            # Caller supplied explicit hex list
            resolved_palette = color_palette
        elif isinstance(color_palette, str) and color_palette in _NAMED_PALETTES:
            resolved_palette = sns.color_palette(color_palette)
        else:
            # Fallback: try seaborn anyway (raises gracefully if unknown)
            try:
                resolved_palette = sns.color_palette(color_palette)
            except Exception:
                resolved_palette = sns.color_palette("deep")

        # ── Clamp bar_width ──────────────────────────────────────────────────
        bar_width = max(0.1, min(1.0, float(bar_width)))
        
        # Check if this is a pie chart (uses the first series only)
        is_pie = any(s.get("type", "").lower().strip() == "pie" for s in series)
        
        if is_pie:
            fig, ax = plt.subplots(figsize=(10, 8))
            fig.patch.set_facecolor(fig_bg)
            ax.set_facecolor(ax_bg)

            pie_series = next(s for s in series if s.get("type", "").lower().strip() == "pie")
            data = pie_series.get("data", [])

            # Universal Sync Guard: Align data and labels
            min_len = min(len(data), len(x_labels))
            plot_data = data[:min_len]
            plot_labels = x_labels[:min_len]

            colors = (
                resolved_palette[:min_len]
                if len(resolved_palette) >= min_len
                else sns.color_palette(resolved_palette if isinstance(resolved_palette, str) else "deep", min_len)
            )
            wedges, texts, autotexts = ax.pie(
                plot_data, labels=plot_labels, autopct='%1.1f%%',
                startangle=140, colors=colors,
                textprops={'fontsize': 12, 'color': text_color}
            )
            for autotext in autotexts:
                autotext.set_fontweight('bold')
                autotext.set_color(text_color)
            plt.title(title, fontsize=20, pad=25, fontweight='bold', color=text_color)
        else:
            fig, ax1 = plt.subplots(figsize=(12, 7))
            fig.patch.set_facecolor(fig_bg)
            ax1.set_facecolor(ax_bg)
            ax1.tick_params(colors=text_color)
            for spine in ax1.spines.values():
                spine.set_edgecolor(grid_color)
            ax2 = None

            # Sync Guard for non-pie charts (ensures X_labels match data points)
            min_x_len = len(x_labels)

            # Assign per-series colours cycling through the resolved palette
            num_series = len(series)
            palette_cycle = (
                resolved_palette * (num_series // len(resolved_palette) + 1)
                if resolved_palette else sns.color_palette("deep", num_series)
            )

            # Iterate and plot each series
            for i, s in enumerate(series):
                label = s.get("label", f"Series {i+1}")
                chart_type = s.get("type", "bar").lower().strip()
                data = s.get("data", [])
                use_secondary = s.get("secondary_y", False)
                series_color = palette_cycle[i]

                # Selection-level Sync Guard: Ensure data doesn't exceed X labels
                plot_data = data[:min_x_len]
                plot_labels = x_labels[:len(plot_data)]

                # Select target axis
                target_ax = ax1
                if use_secondary:
                    if ax2 is None:
                        ax2 = ax1.twinx()
                        ax2.set_facecolor(ax_bg)
                        ax2.tick_params(colors=text_color)
                        for spine in ax2.spines.values():
                            spine.set_edgecolor(grid_color)
                        ax2.grid(False)
                    target_ax = ax2

                if chart_type == "bar":
                    bars = target_ax.bar(
                        plot_labels, plot_data, label=label,
                        alpha=0.85, color=series_color, width=bar_width,
                        edgecolor="none"
                    )
                    if show_data_labels:
                        for bar in bars:
                            val = bar.get_height()
                            target_ax.annotate(
                                f"{val:,.0f}" if val == int(val) else f"{val:,.2f}",
                                xy=(bar.get_x() + bar.get_width() / 2, val),
                                xytext=(0, 4), textcoords="offset points",
                                ha='center', va='bottom',
                                fontsize=9, color=text_color, fontweight='bold'
                            )
                elif chart_type == "barh":
                    bars = target_ax.barh(
                        plot_labels, plot_data, label=label,
                        alpha=0.85, color=series_color, height=bar_width,
                        edgecolor="none"
                    )
                    if show_data_labels:
                        for bar in bars:
                            val = bar.get_width()
                            target_ax.annotate(
                                f"{val:,.0f}" if val == int(val) else f"{val:,.2f}",
                                xy=(val, bar.get_y() + bar.get_height() / 2),
                                xytext=(4, 0), textcoords="offset points",
                                ha='left', va='center',
                                fontsize=9, color=text_color, fontweight='bold'
                            )
                elif chart_type == "line":
                    line_obj, = target_ax.plot(
                        plot_labels, plot_data, label=label,
                        marker="o", linewidth=3, color=series_color
                    )
                    if show_data_labels:
                        for x_pos, y_pos in zip(plot_labels, plot_data):
                            target_ax.annotate(
                                f"{y_pos:,.0f}" if y_pos == int(y_pos) else f"{y_pos:,.2f}",
                                xy=(x_pos, y_pos),
                                xytext=(0, 6), textcoords="offset points",
                                ha='center', va='bottom',
                                fontsize=9, color=text_color
                            )
                elif chart_type == "scatter":
                    target_ax.scatter(
                        plot_labels, plot_data, label=label,
                        s=100, color=series_color, alpha=0.85
                    )
                else:
                    continue

            # Formatting
            ax1.set_title(title, fontsize=20, pad=25, fontweight='bold', color=text_color)
            ax1.xaxis.label.set_color(text_color)
            ax1.yaxis.label.set_color(text_color)

            # For horizontal bars, swap axis label positions for clarity
            is_horizontal = any(s.get("type", "").lower().strip() == "barh" for s in series)
            if is_horizontal:
                if y_label: ax1.set_xlabel(y_label, fontsize=14, color=text_color)
                if x_label: ax1.set_ylabel(x_label, fontsize=14, color=text_color)
            else:
                if x_label: ax1.set_xlabel(x_label, fontsize=14, color=text_color)
                if y_label: ax1.set_ylabel(y_label, fontsize=14, color=text_color)

            if ax2:
                secondary_series = [s for s in series if s.get("secondary_y")]
                if secondary_series:
                    ax2.set_ylabel(
                        secondary_series[0].get("label", ""),
                        fontsize=14, color=text_color
                    )
                ax2.yaxis.label.set_color(text_color)

            # Combine legends
            legend_kwargs = dict(
                loc='upper left', frameon=True,
                facecolor=ax_bg, edgecolor=grid_color,
                labelcolor=text_color
            )
            lines, labels = ax1.get_legend_handles_labels()
            if ax2:
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines + lines2, labels + labels2, **legend_kwargs)
            else:
                ax1.legend(**legend_kwargs)

            if len(x_labels) > 6:
                ax1.tick_params(axis='x', rotation=45, colors=text_color)
                for lbl in ax1.get_xticklabels():
                    lbl.set_ha('right')
                    lbl.set_color(text_color)
            else:
                ax1.tick_params(axis='x', rotation=0, colors=text_color)
                for lbl in ax1.get_xticklabels():
                    lbl.set_color(text_color)
            for lbl in ax1.get_yticklabels():
                lbl.set_color(text_color)
            
        plt.tight_layout()

        import uuid
        filename = f"chart_{uuid.uuid4().hex[:8]}.png"
        filepath = OUTPUT_DIR / filename
        plt.savefig(filepath, dpi=150, facecolor=fig_bg, bbox_inches="tight")
        plt.close()

        return f"<CHART>{filename}</CHART>"
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return f"Error plotting the chart: {str(e)}"
