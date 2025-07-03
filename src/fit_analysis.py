import base64
import logging
import os
import re
import tempfile
from typing import Any

import folium
import httpx
import plotly.graph_objects as go
from fitparse import FitFile
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


def compress_html(html_content: str) -> str:
    """Compress HTML by removing unnecessary whitespace and comments"""
    # Remove HTML comments
    html_content = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)

    # Remove extra whitespace between tags
    html_content = re.sub(r">\s+<", "><", html_content)

    # Remove leading/trailing whitespace from lines
    html_content = "\n".join(line.strip() for line in html_content.split("\n"))

    # Remove empty lines
    html_content = re.sub(r"\n\s*\n", "\n", html_content)

    # Compress inline CSS/JS (basic compression)
    html_content = re.sub(r"\s+", " ", html_content)

    return html_content.strip()


def html_to_base64(html_content: str) -> str:
    """Convert HTML content to base64 encoding"""
    compressed_html = compress_html(html_content)
    return base64.b64encode(compressed_html.encode("utf-8")).decode("ascii")


class FitFileAnalyzer:
    def __init__(self, fit_url: str):
        self.fit_url = fit_url
        self.records: list[dict[str, Any]] = []

    async def download_and_parse(self) -> bool:
        """Download FIT file and extract GPS/elevation data"""
        try:
            # Download FIT file using httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(self.fit_url)
                response.raise_for_status()

            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp_file:
                tmp_file.write(response.content)
                tmp_file_path = tmp_file.name

            # Parse FIT file
            fitfile = FitFile(tmp_file_path)

            # Extract records with GPS and elevation data
            for record in fitfile.get_messages("record"):
                record_data = {}

                for field in record:
                    if field.name in [
                        "position_lat",
                        "position_long",
                        "enhanced_altitude",
                        "altitude",
                        "distance",
                        "timestamp",
                        "heart_rate",
                        "speed",
                        "cadence",
                        "power",
                    ]:
                        record_data[field.name] = field.value

                # Only keep records with GPS coordinates
                if "position_lat" in record_data and "position_long" in record_data:
                    # Convert semicircles to degrees
                    if record_data["position_lat"] and record_data["position_long"]:
                        record_data["lat"] = record_data["position_lat"] * (
                            180 / (2**31)
                        )
                        record_data["lng"] = record_data["position_long"] * (
                            180 / (2**31)
                        )
                        self.records.append(record_data)

            # Clean up temp file
            os.unlink(tmp_file_path)
            logger.info(
                f"Successfully parsed FIT file with {len(self.records)} GPS points"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing FIT file: {e}")
            return False

    def create_route_map(self, save_path: str | None = None) -> folium.Map | None:
        """Generate interactive route map with elevation coloring"""
        if not self.records:
            return None

        # Create base map centered on route
        center_lat = sum(r["lat"] for r in self.records) / len(self.records)
        center_lng = sum(r["lng"] for r in self.records) / len(self.records)

        m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

        # Extract coordinates and elevation for the route
        coordinates = []
        elevations = []

        for record in self.records:
            coordinates.append([record["lat"], record["lng"]])
            # Use enhanced_altitude if available, otherwise altitude
            elevation = record.get("enhanced_altitude") or record.get("altitude", 0)
            elevations.append(elevation)

        # Reduce number of points for better performance (sample every nth point)
        # For large datasets, sample to max 50 segments for MCP responses
        max_segments = 50
        if len(coordinates) > max_segments:
            step = len(coordinates) // max_segments
            coordinates = coordinates[::step]
            elevations = elevations[::step]

        # Create color gradient based on elevation
        if elevations:
            min_elev = min(elevations)
            max_elev = max(elevations)

            # Create segments with elevation-based colors
            for i in range(len(coordinates) - 1):
                if max_elev > min_elev:
                    # Normalize elevation to 0-1 range
                    elev_norm = (elevations[i] - min_elev) / (max_elev - min_elev)
                    # Create color: blue (low) to red (high)
                    color = (
                        f"#{int(255 * elev_norm):02x}{int(255 * (1 - elev_norm)):02x}00"
                    )
                else:
                    color = "#0000FF"  # Blue if no elevation change

                folium.PolyLine(
                    locations=[coordinates[i], coordinates[i + 1]],
                    color=color,
                    weight=4,
                    opacity=0.8,
                ).add_to(m)

        # Add start and end markers
        folium.Marker(
            coordinates[0], popup="Start", icon=folium.Icon(color="green", icon="play")
        ).add_to(m)

        folium.Marker(
            coordinates[-1], popup="End", icon=folium.Icon(color="red", icon="stop")
        ).add_to(m)

        # Add elevation legend
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 50px; width: 120px; height: 60px;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
        <p><b>Elevation</b></p>
        <p>🔴 High: {max_elev:.0f}m</p>
        <p>🔵 Low: {min_elev:.0f}m</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        if save_path:
            m.save(save_path)

        return m

    def create_elevation_chart(self, save_path: str | None = None) -> go.Figure | None:
        """Generate elevation profile chart"""
        if not self.records:
            return None

        # Extract data for chart
        distances = []
        elevations = []
        timestamps = []
        heart_rates = []

        for record in self.records:
            if "distance" in record:
                distances.append(record["distance"] / 1000)  # Convert to km
            else:
                distances.append(len(distances) * 0.01)  # Approximate if no distance

            elevation = record.get("enhanced_altitude") or record.get("altitude", 0)
            elevations.append(elevation)

            if "timestamp" in record:
                timestamps.append(record["timestamp"])

            if "heart_rate" in record:
                heart_rates.append(record["heart_rate"])

        # Sample data to reduce chart size for large datasets
        max_points = 100  # Aggressively reduce chart complexity for MCP
        if len(distances) > max_points:
            step = len(distances) // max_points
            distances = distances[::step]
            elevations = elevations[::step]
            if heart_rates:
                heart_rates = heart_rates[::step]

        # Create subplot with secondary y-axis
        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=("Elevation Profile", "Heart Rate"),
            vertical_spacing=0.1,
            shared_xaxes=True,
        )

        # Elevation profile
        fig.add_trace(
            go.Scatter(
                x=distances,
                y=elevations,
                mode="lines",
                name="Elevation",
                line=dict(color="green", width=2),
                fill="tonexty",
            ),
            row=1,
            col=1,
        )

        # Heart rate (if available)
        if heart_rates:
            fig.add_trace(
                go.Scatter(
                    x=distances[: len(heart_rates)],
                    y=heart_rates,
                    mode="lines",
                    name="Heart Rate",
                    line=dict(color="red", width=2),
                ),
                row=2,
                col=1,
            )

        # Update layout
        fig.update_layout(title="Workout Analysis", height=600, showlegend=True)

        fig.update_xaxes(title_text="Distance (km)", row=2, col=1)
        fig.update_yaxes(title_text="Elevation (m)", row=1, col=1)
        fig.update_yaxes(title_text="Heart Rate (bpm)", row=2, col=1)

        if save_path:
            fig.write_html(save_path)

        return fig

    def get_workout_summary(self) -> dict[str, Any]:
        """Get summary statistics from the workout"""
        if not self.records:
            return {}

        elevations = [
            r.get("enhanced_altitude") or r.get("altitude", 0) for r in self.records
        ]
        distances = [r.get("distance", 0) for r in self.records]
        heart_rates = [r.get("heart_rate") for r in self.records if r.get("heart_rate")]
        powers = [r.get("power") for r in self.records if r.get("power")]
        speeds = [r.get("speed") for r in self.records if r.get("speed")]

        return {
            "total_distance_km": max(distances) / 1000 if distances else 0,
            "elevation_gain_m": sum(
                max(0, elevations[i] - elevations[i - 1])
                for i in range(1, len(elevations))
            ),
            "max_elevation_m": max(elevations) if elevations else 0,
            "min_elevation_m": min(elevations) if elevations else 0,
            "avg_heart_rate": sum(heart_rates) / len(heart_rates)
            if heart_rates
            else None,
            "max_heart_rate": max(heart_rates) if heart_rates else None,
            "avg_power": sum(powers) / len(powers) if powers else None,
            "max_power": max(powers) if powers else None,
            "avg_speed_kmh": (sum(speeds) / len(speeds)) * 3.6 if speeds else None,
            "max_speed_kmh": max(speeds) * 3.6 if speeds else None,
            "total_points": len(self.records),
        }


# MCP integration functions:
async def enhance_workout_with_fit_analysis(
    workout_data: dict[str, Any],
) -> dict[str, Any]:
    """Enhance workout data with FIT file analysis if available"""
    try:
        # Check if workout has a FIT file URL
        fit_url = None
        if workout_data.get("workout_summary"):
            if isinstance(workout_data["workout_summary"], dict):
                fit_url = workout_data["workout_summary"].get("file", {}).get("url")

        if not fit_url:
            logger.debug("No FIT file URL found in workout data")
            return workout_data

        # Create analyzer and parse FIT file
        analyzer = FitFileAnalyzer(fit_url)
        success = await analyzer.download_and_parse()

        if not success:
            logger.warning(f"Failed to parse FIT file from {fit_url}")
            return workout_data

        # Get enhanced summary statistics
        fit_summary = analyzer.get_workout_summary()

        if fit_summary:
            # Add FIT analysis to workout data
            workout_data["fit_analysis"] = {
                "summary_stats": fit_summary,
                "has_gps_data": len(analyzer.records) > 0,
                "gps_points_count": len(analyzer.records),
            }
            logger.info(f"Enhanced workout {workout_data.get('id')} with FIT analysis")

        return workout_data

    except Exception as e:
        logger.error(f"Error enhancing workout with FIT analysis: {e}")
        return workout_data


def format_fit_analysis(fit_analysis: dict[str, Any]) -> str:
    """Format FIT analysis data for display"""
    if not fit_analysis:
        return ""

    stats = fit_analysis.get("summary_stats", {})
    if not stats:
        return ""

    lines = ["📊 **FIT File Analysis:**"]

    # Distance and elevation
    if stats.get("total_distance_km"):
        lines.append(f"  🏃 Total Distance: {stats['total_distance_km']:.2f} km")

    if stats.get("elevation_gain_m"):
        lines.append(f"  ⛰️  Elevation Gain: {stats['elevation_gain_m']:.0f} m")

    if stats.get("max_elevation_m") and stats.get("min_elevation_m"):
        min_elev = stats["min_elevation_m"]
        max_elev = stats["max_elevation_m"]
        lines.append(f"  📏 Elevation Range: {min_elev:.0f} - {max_elev:.0f} m")

    # Heart rate
    if stats.get("avg_heart_rate"):
        hr_text = f"  ❤️ Heart Rate: {stats['avg_heart_rate']:.0f} bpm (avg)"
        if stats.get("max_heart_rate"):
            hr_text += f", {stats['max_heart_rate']:.0f} bpm (max)"
        lines.append(hr_text)

    # Power
    if stats.get("avg_power"):
        power_text = f"  ⚡ Power: {stats['avg_power']:.0f} W (avg)"
        if stats.get("max_power"):
            power_text += f", {stats['max_power']:.0f} W (max)"
        lines.append(power_text)

    # Speed
    if stats.get("avg_speed_kmh"):
        speed_text = f"  🏎️  Speed: {stats['avg_speed_kmh']:.1f} km/h (avg)"
        if stats.get("max_speed_kmh"):
            speed_text += f", {stats['max_speed_kmh']:.1f} km/h (max)"
        lines.append(speed_text)

    # GPS data info
    if fit_analysis.get("has_gps_data"):
        lines.append(f"  🗺️  GPS Points: {fit_analysis.get('gps_points_count', 0):,}")

    return "\n".join(lines)


# Usage example:
if __name__ == "__main__":
    import asyncio

    async def main():
        # Example FIT file URL (replace with actual URL from your Wahoo data)
        fit_url = "https://cdn.wahooligan.com/wahoo-cloud/production/uploads/workout_file/file/C46hy3Pjl1QtdACu1PuRng/2025-07-03-052741-ELEMNT_ROAM_F206-58-0.fit"

        try:
            analyzer = FitFileAnalyzer(fit_url)
            success = await analyzer.download_and_parse()

            if not success:
                print("Failed to download and parse FIT file")
                return

            # Create route map
            route_map = analyzer.create_route_map("route_map.html")
            if route_map:
                print("Route map saved as 'route_map.html'")

            # Create elevation chart
            elevation_chart = analyzer.create_elevation_chart("elevation_chart.html")
            if elevation_chart:
                print("Elevation chart saved as 'elevation_chart.html'")

            # Print summary
            summary = analyzer.get_workout_summary()
            print("Workout Summary:", summary)

            # Test formatting
            fit_analysis = {
                "summary_stats": summary,
                "has_gps_data": len(analyzer.records) > 0,
                "gps_points_count": len(analyzer.records),
            }
            formatted = format_fit_analysis(fit_analysis)
            print("\nFormatted Analysis:")
            print(formatted)

        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(main())
