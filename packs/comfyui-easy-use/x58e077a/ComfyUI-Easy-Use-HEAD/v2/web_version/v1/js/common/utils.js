import { comfy } from '/comfy/api/v2.js';

// The pack's own copy of the DOM builder it used to import from
// scripts/ui.js. Same call shape, so its call sites are unchanged.
export function $el(tag, propsOrChildren, children) {
    const split = tag.split(".");
    const element = document.createElement(split.shift());
    if (split.length > 0) element.classList.add(...split);
    if (propsOrChildren) {
        if (typeof propsOrChildren === "string") propsOrChildren = { textContent: propsOrChildren };
        else if (propsOrChildren instanceof Element) propsOrChildren = [propsOrChildren];
        if (Array.isArray(propsOrChildren)) element.append(...propsOrChildren.filter(Boolean));
        else {
            const { parent, $: cb, dataset, style, ...rest } = propsOrChildren;
            if (rest.for) element.setAttribute("for", rest.for);
            if (style) Object.assign(element.style, style);
            if (dataset) Object.assign(element.dataset, dataset);
            Object.assign(element, rest);
            if (children) element.append(...children.filter(Boolean));
            if (parent) parent.append(element);
            if (cb) cb(element);
        }
    }
    return element;
}

export function sleep(ms = 100, value) {
    return new Promise((resolve) => {
        setTimeout(() => {
            resolve(value);
        }, ms);
    });
}
export function addPreconnect(href, crossorigin=false){
    const preconnect = document.createElement("link");
    preconnect.rel = 'preconnect'
    preconnect.href = href
    if(crossorigin) preconnect.crossorigin = ''
    document.head.appendChild(preconnect);
}
export function addCss(href, base=true) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.type = "text/css";
    link.href =  base ? "extensions/ComfyUI-Easy-Use/"+href : href;
    document.head.appendChild(link);
}

export function addMeta(name, content) {
    const meta = document.createElement("meta");
    meta.setAttribute("name", name);
    meta.setAttribute('content', content);
    document.head.appendChild(meta);
}

export function deepEqual(obj1, obj2) {
  if (typeof obj1 !== typeof obj2) {
    return false
  }
  if (typeof obj1 !== 'object' || obj1 === null || obj2 === null) {
    return obj1 === obj2
  }
  const keys1 = Object.keys(obj1)
  const keys2 = Object.keys(obj2)
  if (keys1.length !== keys2.length) {
    return false
  }
  for (let key of keys1) {
    if (!deepEqual(obj1[key], obj2[key])) {
      return false
    }
  }
  return true
}


export function getLocale(){
    const locale = localStorage['AGL.Locale'] || localStorage['Comfy.Settings.AGL.Locale'] || 'en-US'
    return locale
}

export function spliceExtension(fileName){
   return fileName.substring(0,fileName.lastIndexOf('.'))
}
export function getExtension(fileName){
   return fileName.substring(fileName.lastIndexOf('.') + 1)
}

export function formatTime(time, format) {
  time = typeof (time) === "number" ? time : (time instanceof Date ? time.getTime() : parseInt(time));
  if (isNaN(time)) return null;
  if (typeof (format) !== 'string' || !format) format = 'yyyy-MM-dd hh:mm:ss';
  let _time = new Date(time);
  time = _time.toString().split(/[\s\:]/g).slice(0, -2);
  time[1] = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'][_time.getMonth()];
  let _mapping = {
    MM: 1,
    dd: 2,
    yyyy: 3,
    hh: 4,
    mm: 5,
    ss: 6
  };
  return format.replace(/([Mmdhs]|y{2})\1/g, (key) => time[_mapping[key]]);
}


export const findWidgetByName = (node, name) => node.widgets.get(name);

export const doesInputWithNameExist = (node, name) => node.inputs.names().includes(name);

export function updateNodeHeight(node) {node.setSizeConstraints({autoHeight: true});}

export function toggleWidget(node, widget, show = false, suffix = "") {
	if (!widget || doesInputWithNameExist(node, widget.name)) return;
	widget.setHidden(!show);

	if (show) node.setSizeConstraints({autoHeight: true});
}

export function isLocalNetwork(ip) {
  const localNetworkRanges = [
    '192.168.',
    '10.',
    '127.',
    /^172\.((1[6-9]|2[0-9]|3[0-1])\.)/
  ];

  return localNetworkRanges.some(range => {
    if (typeof range === 'string') {
      return ip.startsWith(range);
    } else {
      return range.test(ip);
    }
  });
}


/**
* accAdd 高精度加法
* @since 1.0.10
* @param {Number} arg1
* @param {Number} arg2
* @return {Number}
*/
export function accAdd(arg1, arg2) {
  let r1, r2, s1, s2,max;
  s1 = typeof arg1 == 'string' ? arg1 : arg1.toString()
  s2 = typeof arg2 == 'string' ? arg2 : arg2.toString()
  try { r1 = s1.split(".")[1].length } catch (e) { r1 = 0 }
  try { r2 = s2.split(".")[1].length } catch (e) { r2 = 0 }
  max = Math.pow(10, Math.max(r1, r2))
  return (arg1 * max + arg2 * max) / max
}
/**
 * accSub 高精度减法
 * @since 1.0.10
 * @param {Number} arg1
 * @param {Number} arg2
 * @return {Number}
 */
export function accSub(arg1, arg2) {
  let r1, r2, max, min,s1,s2;
  s1 = typeof arg1 == 'string' ? arg1 : arg1.toString()
  s2 = typeof arg2 == 'string' ? arg2 : arg2.toString()
  try { r1 = s1.split(".")[1].length } catch (e) { r1 = 0 }
  try { r2 = s2.split(".")[1].length } catch (e) { r2 = 0 }
  max = Math.pow(10, Math.max(r1, r2));
  //动态控制精度长度
  min = (r1 >= r2) ? r1 : r2;
  return ((arg1 * max - arg2 * max) / max).toFixed(min)
}
/**
 * accMul 高精度乘法
 * @since 1.0.10
 * @param {Number} arg1
 * @param {Number} arg2
 * @return {Number}
 */
export function accMul(arg1, arg2) {
  let max = 0, s1 =  typeof arg1 == 'string' ? arg1 : arg1.toString(), s2 = typeof arg2 == 'string' ? arg2 : arg2.toString();
  try { max += s1.split(".")[1].length } catch (e) { }
  try { max += s2.split(".")[1].length } catch (e) { }
  return Number(s1.replace(".", "")) * Number(s2.replace(".", "")) / Math.pow(10, max)
}
/**
 * accDiv 高精度除法
 * @since 1.0.10
 * @param {Number} arg1
 * @param {Number} arg2
 * @return {Number}
 */
export function accDiv(arg1, arg2) {
  let t1 = 0, t2 = 0, r1, r2,s1 =  typeof arg1 == 'string' ? arg1 : arg1.toString(), s2 = typeof arg2 == 'string' ? arg2 : arg2.toString();
  try { t1 = s1.toString().split(".")[1].length } catch (e) { }
  try { t2 = s2.toString().split(".")[1].length } catch (e) { }
  r1 = Number(s1.toString().replace(".", ""))
  r2 = Number(s2.toString().replace(".", ""))
  return (r1 / r2) * Math.pow(10, t2 - t1)
}
Number.prototype.div = function (arg) {
  return accDiv(this, arg);
}