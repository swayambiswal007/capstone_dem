document.addEventListener("DOMContentLoaded", async () => {
    const terrainError = document.getElementById("terrainError");
    const blueprintError = document.getElementById("blueprintError");

    const showError = (el, msg) => {
        if (el) {
            el.textContent = msg;
            el.style.display = "block";
        }
        console.error(msg);
    };

    if (typeof Plotly === "undefined") {
        showError(terrainError, "Plotly failed to load. Check your internet connection.");
        showError(blueprintError, "Plotly failed to load. Check your internet connection.");
        return;
    }

    try {
        const response = await fetch("/api/scene", { cache: "no-store" });
        const data = await response.json();

        if (!response.ok || data.error) {
            throw new Error(data.error || `API returned HTTP ${response.status}`);
        }

        // ---------------- TERRAIN ----------------
        const terrain = data.terrain;
        const lake = data.lake_points || [];

        const terrainTrace = {
            x: terrain.x,
            y: terrain.y,
            z: terrain.z,
            type: "surface",
            name: "Copernicus GLO-30 DEM",
            colorscale: [
                [0.00, "#20291f"],
                [0.18, "#39432f"],
                [0.36, "#5b5b42"],
                [0.55, "#817455"],
                [0.72, "#a28f69"],
                [0.87, "#b9a97d"],
                [1.00, "#ded2ad"]
            ],
            showscale: false,
            lighting: {
                ambient: 0.48,
                diffuse: 0.80,
                specular: 0.16,
                roughness: 0.86
            },
            contours: {
                z: {
                    show: true,
                    color: "rgba(35,48,38,.30)",
                    width: 1
                }
            },
            hovertemplate:
                "<b>Copernicus GLO-30</b><br>" +
                "Longitude: %{x:.5f}<br>" +
                "Latitude: %{y:.5f}<br>" +
                "Elevation: %{z:.1f} m<extra></extra>"
        };

        const lakeTrace = {
            x: lake.map(p => p.x),
            y: lake.map(p => p.y),
            z: lake.map(p => p.z + 7),
            type: "scatter3d",
            mode: "markers",
            name: "DINOv2 Prediction",
            marker: {
                size: 6,
                color: "#29d5e7",
                opacity: 1
            },
            hovertemplate:
                "<b>DINOv2 Predicted Lake</b><br>" +
                "Elevation: %{z:.1f} m<extra></extra>"
        };

        const defaultCamera = {
            eye: { x: 1.55, y: 1.45, z: 1.12 },
            up: { x: 0, y: 0, z: 1 }
        };

        await Plotly.newPlot(
            "terrain",
            [terrainTrace, lakeTrace],
            {
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                margin: { l: 0, r: 0, t: 0, b: 0 },
                showlegend: false,
                scene: {
                    bgcolor: "rgba(0,0,0,0)",
                    xaxis: {
                        title: "Longitude",
                        color: "#78909f",
                        gridcolor: "#203542",
                        zeroline: false
                    },
                    yaxis: {
                        title: "Latitude",
                        color: "#78909f",
                        gridcolor: "#203542",
                        zeroline: false
                    },
                    zaxis: {
                        title: "Elevation (m)",
                        color: "#78909f",
                        gridcolor: "#203542",
                        zeroline: false
                    },
                    camera: defaultCamera,
                    aspectmode: "manual",
                    aspectratio: { x: 1.12, y: 0.95, z: 0.72 }
                }
            },
            { responsive: true, displaylogo: false, scrollZoom: true }
        );

        terrainError.style.display = "none";

        document.getElementById("resetMap").onclick = () =>
            Plotly.relayout("terrain", { "scene.camera": defaultCamera });

        document.getElementById("topMap").onclick = () =>
            Plotly.relayout("terrain", {
                "scene.camera": {
                    eye: { x: 0.01, y: 0.01, z: 2.45 },
                    up: { x: 0, y: 1, z: 0 }
                }
            });

        // ---------------- ACTUAL BLUEPRINT ----------------
        const bp = data.blueprint;

        if (!bp) {
            throw new Error("No lake footprint was generated from prediction.tif.");
        }

        const surface = {
            x: bp.x,
            y: bp.y,
            z: bp.z,
            type: "surface",
            name: "DINOv2 Lake Footprint",
            colorscale: [
                [0.00, "#06131b"],
                [0.25, "#09242e"],
                [0.55, "#0d4652"],
                [1.00, "#27d5e7"]
            ],
            showscale: false,
            opacity: 0.78,
            connectgaps: false,
            lighting: {
                ambient: 0.78,
                diffuse: 0.30,
                specular: 0.18,
                roughness: 0.68
            },
            contours: {
                x: {
                    show: true,
                    color: "rgba(91,235,244,.22)",
                    width: 1
                },
                y: {
                    show: true,
                    color: "rgba(91,235,244,.22)",
                    width: 1
                }
            },
            hovertemplate:
                "Easting: %{x:.1f} m<br>" +
                "Northing: %{y:.1f} m<br>" +
                "Relative elevation: %{z:.1f} m<extra></extra>"
        };

        // Derive boundary cells from the actual binary footprint.
        const z = bp.z;
        const x = bp.x;
        const y = bp.y;
        const bx = [];
        const by = [];
        const bz = [];

        const valid = (r, c) =>
            r >= 0 && r < z.length &&
            c >= 0 && c < z[r].length &&
            z[r][c] !== null &&
            Number.isFinite(z[r][c]);

        for (let r = 0; r < z.length; r++) {
            for (let c = 0; c < z[r].length; c++) {
                if (!valid(r, c)) continue;

                const edge =
                    !valid(r - 1, c) ||
                    !valid(r + 1, c) ||
                    !valid(r, c - 1) ||
                    !valid(r, c + 1);

                if (edge) {
                    bx.push(x[c]);
                    by.push(y[r]);
                    bz.push(z[r][c] + 5);
                }
            }
        }

        const boundary = {
            x: bx,
            y: by,
            z: bz,
            type: "scatter3d",
            mode: "markers",
            name: "DINOv2 Boundary",
            marker: {
                size: 3.5,
                color: "#a4f8fb",
                opacity: 0.95
            },
            hoverinfo: "skip"
        };

        await Plotly.newPlot(
            "blueprint",
            [surface, boundary],
            {
                paper_bgcolor: "rgba(0,0,0,0)",
                plot_bgcolor: "rgba(0,0,0,0)",
                margin: { l: 0, r: 0, t: 0, b: 0 },
                showlegend: false,
                scene: {
                    bgcolor: "rgba(0,0,0,0)",
                    xaxis: {
                        title: "Easting (m)",
                        color: "#66828e",
                        gridcolor: "rgba(41,213,231,.13)",
                        zeroline: false
                    },
                    yaxis: {
                        title: "Northing (m)",
                        color: "#66828e",
                        gridcolor: "rgba(41,213,231,.13)",
                        zeroline: false
                    },
                    zaxis: {
                        title: "Relative Elevation (m)",
                        color: "#66828e",
                        gridcolor: "rgba(41,213,231,.08)",
                        zeroline: false
                    },
                    camera: {
                        eye: { x: 1.18, y: 1.18, z: 0.62 },
                        up: { x: 0, y: 0, z: 1 }
                    },
                    aspectmode: "manual",
                    aspectratio: { x: 1.45, y: 0.95, z: 0.48 }
                }
            },
            { responsive: true, displaylogo: false, scrollZoom: true }
        );

        blueprintError.style.display = "none";

        document.getElementById("bpTop").onclick = () =>
            Plotly.relayout("blueprint", {
                "scene.camera": {
                    eye: { x: 0.01, y: 0.01, z: 2.5 },
                    up: { x: 0, y: 1, z: 0 }
                }
            });

        document.getElementById("bp3d").onclick = () =>
            Plotly.relayout("blueprint", {
                "scene.camera": {
                    eye: { x: 1.18, y: 1.18, z: 0.62 },
                    up: { x: 0, y: 0, z: 1 }
                }
            });

        // Real geometry statistics.
        const area = Number(bp.area_m2 || 0);
        document.getElementById("lakeArea").textContent =
            (area / 1e6).toFixed(3) + " km²";
        document.getElementById("lakeLength").textContent =
            Number(bp.length_m || 0).toFixed(0) + " m";
        document.getElementById("lakeWidth").textContent =
            Number(bp.width_m || 0).toFixed(0) + " m";
        document.getElementById("lakeMean").textContent =
            Number(bp.center_elevation || 0).toFixed(0) + " m";
        document.getElementById("maskPixels").textContent =
            data.lake_pixel_count;

    } catch (err) {
        showError(terrainError, "Visualization error: " + err.message);
        showError(blueprintError, "Blueprint error: " + err.message);
    }

    // ---------------- DATASET UPLOAD ----------------
    const file = document.getElementById("file");
    const predict = document.getElementById("predict");
    const fileInfo = document.getElementById("fileInfo");

    file.onchange = () => {
        if (!file.files.length) return;

        fileInfo.style.display = "flex";
        document.getElementById("fileName").textContent = file.files[0].name;
        document.getElementById("uploadTitle").textContent = "Dataset selected";
        document.getElementById("uploadText").textContent = "Ready for model inference";
        document.getElementById("modelStatus").textContent = "Dataset loaded";
        predict.disabled = false;
    };

    document.getElementById("remove").onclick = () => {
        file.value = "";
        fileInfo.style.display = "none";
        document.getElementById("uploadTitle").textContent = "Upload dataset";
        document.getElementById("uploadText").textContent = "Historical lake features";
        document.getElementById("modelStatus").textContent = "Upload a dataset to begin";
        predict.disabled = true;
    };

    predict.onclick = () => {
        predict.disabled = true;
        predict.textContent = "◌ Processing historical record";
        document.getElementById("modelStatus").textContent =
            "Frontend demo — model endpoint not connected yet";

        setTimeout(() => {
            const score = 72;
            document.getElementById("score").textContent = score + "%";
            document.getElementById("level").textContent = "Moderate–High";
            document.getElementById("desc").textContent =
                "Demo output. Connect this panel to the trained temporal GLOF model.";
            document.getElementById("state").textContent = "DEMO";
            document.getElementById("ring").style.background =
                `radial-gradient(circle,#091721 55%,transparent 56%),` +
                `conic-gradient(#29d5e7 ${score * 3.6}deg,#1a2c37 0deg)`;

            document.getElementById("modelStatus").textContent =
                "Frontend demonstration complete";
            predict.disabled = false;
            predict.textContent = "⚡ Run GLOF Prediction";
        }, 900);
    };
});
