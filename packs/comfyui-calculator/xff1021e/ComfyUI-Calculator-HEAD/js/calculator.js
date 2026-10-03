import { app } from "../../../scripts/app.js";

app.registerExtension({
    name: "Comfy.Calculator",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "Calculator") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

                // Create the calculator UI
                const container = document.createElement("div");
                container.style.display = "flex";
                container.style.flexDirection = "column";
                container.style.gap = "5px";
                container.style.padding = "10px";
                container.style.backgroundColor = "#222";
                container.style.borderRadius = "8px";
                container.style.width = "220px";
                container.style.boxSizing = "border-box";

                const display = document.createElement("div");
                display.style.backgroundColor = "#444";
                display.style.color = "#0f0";
                display.style.padding = "10px";
                display.style.textAlign = "right";
                display.style.fontSize = "20px";
                display.style.fontFamily = "monospace";
                display.style.borderRadius = "4px";
                display.style.marginBottom = "5px";
                display.style.minHeight = "44px";
                display.style.display = "flex";
                display.style.alignItems = "center";
                display.style.justifyContent = "flex-end";
                display.style.overflow = "hidden";
                display.textContent = "0";
                container.appendChild(display);

                const buttons = [
                    "7", "8", "9", "/",
                    "4", "5", "6", "*",
                    "1", "2", "3", "-",
                    "0", ".", "C", "+",
                    "="
                ];

                const grid = document.createElement("div");
                grid.style.display = "grid";
                grid.style.gridTemplateColumns = "repeat(4, 1fr)";
                grid.style.gap = "5px";

                let currentExpression = "";
                let isResult = false;

                const updateDisplay = (val) => {
                    let text = val || "0";
                    if (text.length > 15) {
                        text = text.substring(0, 15);
                    }
                    display.textContent = text;
                };

                buttons.forEach(btn => {
                    const button = document.createElement("button");
                    button.textContent = btn;
                    button.style.padding = "15px 5px";
                    button.style.cursor = "pointer";
                    button.style.border = "none";
                    button.style.borderRadius = "4px";
                    button.style.backgroundColor = isNaN(btn) && btn !== "." ? "#555" : "#777";
                    button.style.color = "white";
                    button.style.fontSize = "16px";
                    button.style.fontWeight = "bold";

                    if (btn === "=") {
                        button.style.gridColumn = "span 4";
                        button.style.backgroundColor = "#447744"; // Slight green for equals
                    }

                    button.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (btn === "C") {
                            currentExpression = "";
                            isResult = false;
                            updateDisplay("0");
                        } else if (btn === "=") {
                            try {
                                const result = eval(currentExpression.replace(/[^0-9+\-*/.]/g, ''));
                                updateDisplay(result.toString());
                                currentExpression = result.toString();
                                isResult = true;
                            } catch (e) {
                                updateDisplay("Error");
                                currentExpression = "";
                            }
                        } else {
                            if (isResult) {
                                if (!isNaN(btn)) {
                                    currentExpression = btn;
                                } else {
                                    currentExpression += btn;
                                }
                                isResult = false;
                            } else {
                                currentExpression += btn;
                            }
                            updateDisplay(currentExpression);
                        }
                    };
                    grid.appendChild(button);
                });

                container.appendChild(grid);
                
                // Add as a DOM widget
                const widget = this.addDOMWidget("calc_ui", "calc", container);
                
                // Final size adjustment to ensure no obstruction
                this.setSize([240, 360]);
                
                return r;
            };
        }
    },
});
