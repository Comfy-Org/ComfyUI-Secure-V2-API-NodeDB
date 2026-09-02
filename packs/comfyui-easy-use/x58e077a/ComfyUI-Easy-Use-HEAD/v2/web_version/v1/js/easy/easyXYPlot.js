import { comfy } from '/comfy/api/v2.js'
import {removeDropdown, createDropdown} from "../common/dropdown.js";

function generateNumList(dictionary) {
  const minimum = dictionary["min"] || 0;
  const maximum = dictionary["max"] || 0;
  const step = dictionary["step"] || 1;

  if (step === 0) {
    return [];
  }

  const result = [];
  let currentValue = minimum;

  while (currentValue <= maximum) {
    if (Number.isInteger(step)) {
      result.push(Math.round(currentValue) + '; ');
    } else {
      let formattedValue = currentValue.toFixed(3);
      if(formattedValue == -0.000){
        formattedValue = '0.000';
      }
      if (!/\.\d{3}$/.test(formattedValue)) {
        formattedValue += "0";
      }
      result.push(formattedValue + "; ");
    }
    currentValue += step;
  }

  if (maximum >= 0 && minimum >= 0) {
	//low to high
	return result;
  }
  else {
	//high to low
    return result.reverse();
  }
}

let plotDict = {};
let currentOptionsDict = {};

function getCurrentOptionLists(widget) {
	const widgetName = widget.name;
	const widgetValue = String(widget.getValue()).replace(/^(loader|preSampling):\s/, '');

	if (!currentOptionsDict[widgetName]) {
	  currentOptionsDict = {...currentOptionsDict, [widgetName]: plotDict[widgetValue]};
	}  else if (currentOptionsDict[widgetName] != plotDict[widgetValue]) {
	  currentOptionsDict[widgetName] = plotDict[widgetValue];
	}
}

function addChangeListeners(node) {
	for (const w of node.widgets) {
		if (w.name === "x_axis" ||
				w.name === "y_axis") {
			w.on('change', () => getCurrentOptionLists(w));
			getCurrentOptionLists(w);
		}
	}
}

function dropdownCreator(node) {
	const widgets = node.widgets.all().filter((w) => {
		const options = w.getOptions();
		return (w.widgetType === "customtext" && options?.dynamicPrompts !== false) || options?.dynamicPrompts;
	});

	for (const w of widgets) {
		let inputEl;
		let unsubscribe;

		function replaceOptionSegments(selectedOption, inputSegments, cursorSegmentIndex, optionsList) {
			if (selectedOption) {
				inputSegments[cursorSegmentIndex] = selectedOption;
			}

			return inputSegments.map(segment => verifySegment(segment, optionsList))
									 .filter(item => item !== '')
									 .join('');
		}

		function verifySegment(segment, optionsList) {
			segment = cleanSegment(segment);

			if (isInOptionsList(segment, optionsList)) {
				return segment + '; ';
			}

			let matchedOptions = findMatchedOptions(segment, optionsList);

			if (matchedOptions.length === 1 || matchedOptions.length === 2) {
				return matchedOptions[0];
			}

			if (isInOptionsList(formatNumberSegment(segment), optionsList)) {
				return formatNumberSegment(segment) + '; ';
			}

			return '';
		}

		function cleanSegment(segment) {
			return segment.replace(/(\n|;| )/g, '');
		}

		function isInOptionsList(segment, optionsList) {
			return optionsList.includes(segment + '; ');
		}

		function findMatchedOptions(segment, optionsList) {
			return optionsList.filter(option => option.toLowerCase().includes(segment.toLowerCase()));
		}

		function formatNumberSegment(segment) {
			if (Number(segment)) {
				return Number(segment).toFixed(3);
			}

			if (['0', '0.', '0.0', '0.00', '00'].includes(segment)) {
				return '0.000';
			}
			return segment;
		}

		const onInput = function () {
			w.setValue(inputEl.value);
			const axisWidgetName = w.name[0] + '_axis';
			let optionsList = currentOptionsDict?.[axisWidgetName] || [];
			if (optionsList.length === 0) {return}

			const inputText = inputEl.value;
			const cursorPosition = inputEl.selectionStart;
			let inputSegments = inputText.split('; ');

			const cursorSegmentIndex = inputText.substring(0, cursorPosition).split('; ').length - 1;
			const currentSegment = inputSegments[cursorSegmentIndex];
			const currentSegmentLower = currentSegment.replace(/\n/g, '').toLowerCase();
			const filteredOptionsList = optionsList.filter(option => option.toLowerCase().includes(currentSegmentLower)).map(option => option.replace(/; /g, ''));

			if (filteredOptionsList.length > 0) {
				createDropdown(inputEl, filteredOptionsList, (selectedOption) => {
					const verifiedText = replaceOptionSegments(selectedOption, inputSegments, cursorSegmentIndex, optionsList);
					inputEl.value = verifiedText;
					w.setValue(verifiedText);
				});
			}
			else {
				removeDropdown();
				const verifiedText = replaceOptionSegments(null, inputSegments, cursorSegmentIndex, optionsList);
				inputEl.value = verifiedText;
				w.setValue(verifiedText);
			}
		};

		w.setHidden(true);
		node.widgets.mount({
			name: w.name + '_autocomplete',
			render(container) {
				inputEl = document.createElement('textarea');
				inputEl.value = String(w.getValue() ?? '');
				inputEl.style.width = '100%';
				inputEl.style.height = '100%';
				container.appendChild(inputEl);
				inputEl.addEventListener('input', onInput);
				inputEl.addEventListener('mouseup', onInput);
				unsubscribe = w.on('change', (value) => {
					const nextValue = String(value ?? '');
					if (inputEl.value !== nextValue) inputEl.value = nextValue;
				});
			},
			destroy() {
				inputEl?.removeEventListener('input', onInput);
				inputEl?.removeEventListener('mouseup', onInput);
				unsubscribe?.();
				removeDropdown();
			},
		});
	}
}

comfy.defs.extend('easy XYPlot', (b) => {
	const hiddenPlotDict = b.def.hidden.plot_dict;
	if (!Array.isArray(hiddenPlotDict) || typeof hiddenPlotDict[0] !== 'object' || hiddenPlotDict[0] === null) return;

	plotDict = {...hiddenPlotDict[0]};
	for (const key in plotDict) {
		const value = plotDict[key];
		if (Array.isArray(value)) {
			let updatedValues = [];
			for (const v of value) {
				updatedValues.push(v + '; ');
			}
			plotDict[key] = updatedValues;
		} else if (typeof(value) === 'object') {
			if(key == 'seed'){
				plotDict[key] = value + '; ';
			}
			else {
				plotDict[key] = generateNumList(value);
			}
		} else {
			plotDict[key] = value + '; ';
		}
	}
	plotDict["None"] = [];
	plotDict["---------------------"] = [];

	b.onCreated((node) => {
		addChangeListeners(node);
		dropdownCreator(node);
	});
});
