import { comfy } from '/comfy/api/v2.js';

/*
Is this a UE node?
*/
export function is_ue_type(type) {
    if (type == "Anything Everywhere") return true;
    return ((type) && (type.startsWith("Anything Everywhere") || type==="Seed Everywhere" || type==="Prompts Everywhere"))
}

/* The same test written as a def selector, for comfy.defs.extend. */
export const UE_TYPES = /^(Anything Everywhere.*|Seed Everywhere|Prompts Everywhere)$/

export class Logger {
    static LIMITED_LOG_BLOCKED = false;
    static LIMITED_LOG_MS      = 5000;
    static level;  // 0 for errors only, 1 activates 'log_problem', 2 activates 'log_info', 3 activates 'log_detail'

    static log_arguments(a) {
        Object.keys(arguments).forEach((k)=>{console.log(arguments[k])})
    }

    static log_error(message, more) {
        if (more) console.log(more)
        console.error(message)
    }

    static log(message, foreachable, limited) {
        if (limited && Logger.check_limited()) return false
        console.log(message);
        foreachable?.forEach((x)=>{console.log(x)})
        return true
    }

    static log_with_trace() {
        if (Logger.log(arguments)) console.trace()
    }

    static check_limited() {
        if (Logger.LIMITED_LOG_BLOCKED) return true
        Logger.LIMITED_LOG_BLOCKED = true
        setTimeout( ()=>{Logger.LIMITED_LOG_BLOCKED = false}, Logger.LIMITED_LOG_MS )
        return false
    }

    static null() {}

    static level_changed(new_level) {
        Logger.level = new_level
        Logger.log_detail  = (Logger.level>=3) ? Logger.log : Logger.null
        Logger.log_info    = (Logger.level>=2) ? Logger.log : Logger.null
        Logger.log_problem = (Logger.level>=1) ? Logger.log_with_trace : Logger.null
    }

    static log_detail(){}
    static log_info(){}
    static log_problem(){}
}

/*
Is a node alive (ie not bypassed or set to never)?

ResolvedNodeView.mode and UnconnectedInput.nodeMode both carry litegraph's
number; the names are accepted because a NodeHandle spells the same thing that
way.
*/
export function mode_is_live(mode, treat_bypassed_as_live){
    if (mode===0 || mode==='always') return true;
    if (mode===2 || mode===4 || mode==='never' || mode==='bypass') return !!treat_bypassed_as_live;
    Logger.log_error(`node mode ${mode} - I only understand always, never and bypass`);
    return true;
}

export function bypassed_counts_as_live() {
    return !!comfy.settings.get("Use Everywhere.Options.connect_to_bypassed")
}

/*
The per-node opt-in - is_connectable() in the original, read off a candidate
from the supply view rather than a live node. `isWidgetInput` is the published
form of `input.widget`, and the flags travel in the candidate's own properties.
*/
export function candidate_is_connectable(candidate) {
    if (candidate.nodeProperties.rejects_ue_links) return false
    const ue = candidate.nodeProperties.ue_properties
    if (candidate.isWidgetInput) return !!(ue?.widget_ue_connectable?.[candidate.name])
    return !(ue?.input_ue_unconnectable?.[candidate.name])
}

const ALL_REGEXES = ['title', 'input', 'prompt', 'negative', 'group']

function regex_for(props, key) {
  const source = props[`${key}_regex`]
  if (!source || source=='.*') return null
  try {
    return { regex:new RegExp(source), invert:!!props[`${key}_regex_invert`] }
  } catch (error) {
    Logger.log_error(error)
    return null
  }
}

function duplicate_types(slots) {
  const seen = new Set()
  const duplicated = new Set()
  slots.forEach((slot)=>{
    if (seen.has(slot.type)) duplicated.add(slot.type)
    seen.add(slot.type)
  })
  return duplicated
}

function priority_for(type, props, duplicated) {
  var priority = 10
  if (type=="Seed Everywhere" || type=="Prompts Everywhere") priority += 10
  if (ALL_REGEXES.some((key)=>props[`${key}_regex`]) || duplicated.size) priority += 20
  if (props.group_restricted > 0) priority += 3
  if (props.color_restricted > 0) priority += 6
  return priority
}

function repeated_type_test(rule, name) {
  if (rule==1) return (candidate)=>candidate.label.startsWith(name) || name.startsWith(candidate.label)
  if (rule==2) return (candidate)=>candidate.label.endsWith(name) || name.endsWith(candidate.label)
  if (rule==3) return (candidate)=>candidate.nodeTitle==name
  if (rule==4) return (candidate)=>{
    try { return !!new RegExp(name).exec(candidate.label) }
    catch (error) { Logger.log_error(error); return false }
  }
  return (candidate)=>candidate.label==name
}

export function broadcasts_from(self, props) {
  const from_outputs = props.seed_inputs || self.properties.ue_convert
  const slots = from_outputs
    ? self.outputs
        .filter((slot)=>props.seed_inputs ? slot.index==0 : !props.output_not_broadcasting?.[slot.name])
        .map((slot)=>({ ...slot, type:props.seed_inputs ? "INT" : slot.type, from:{output:slot.index}, sourceNodeId:self.id }))
    : self.inputs
        .filter((slot)=>slot.connectedType)
        .map((slot)=>({ ...slot, type:slot.connectedType, from:{forwardInput:slot.index} }))
  const duplicated = duplicate_types(slots)
  const restrictions = {
    title_regex:regex_for(props, 'title'), input_regex:regex_for(props, 'input'),
    group_regex:regex_for(props, 'group'), group_restricted:props.group_restricted,
    color_restricted:props.color_restricted, groups:self.groups, color:self.color,
    string_to_combo:props.string_to_combo > 0, send_to_any:props.send_to_any > 0,
    priority:props.priority || priority_for(self.type, props, duplicated)
  }
  return slots.map((slot)=>{
    const repeated = !props.seed_inputs && (duplicated.has(slot.type) || props.apply_to_unrepeated)
    return {
      ...restrictions, from:slot.from, type:slot.type, sourceNodeId:slot.sourceNodeId,
      additional_requirement:repeated ? repeated_type_test(props.repeated_type_rule || 0, slot.label || slot.name) : null,
      description:`${self.type} #${self.id} slot ${slot.index} "${slot.type}" (priority ${restrictions.priority})`
    }
  })
}

export function display_name(candidate) {
  return candidate.nodeTitle || candidate.nodeType || candidate.nodeProperties?.['Node name for S&R'] || "un-nameable node"
}

function shares_group(mine, theirs) {
  return theirs.some((their)=>mine.some((my)=>my.id==their.id))
}

export function broadcast_matches(broadcast, candidate) {
  if (broadcast.additional_requirement && !broadcast.additional_requirement(candidate)) return false
  if (broadcast.sourceNodeId==candidate.nodeId) return false
  if (broadcast.type!=candidate.type &&
      !(broadcast.type=="STRING" && candidate.type=="COMBO" && broadcast.string_to_combo) &&
      !(candidate.type=="*" && broadcast.send_to_any)) return false
  const shared_group = shares_group(broadcast.groups, candidate.nodeGroups)
  if (broadcast.group_restricted==1 && !shared_group) return false
  if (broadcast.group_restricted==2 && shared_group) return false
  if (broadcast.color_restricted==1 && candidate.nodeColor!=broadcast.color) return false
  if (broadcast.color_restricted==2 && candidate.nodeColor==broadcast.color) return false
  if (broadcast.group_regex && !candidate.nodeGroups.some((group)=>broadcast.group_regex.regex.test(group.title)!=broadcast.group_regex.invert)) return false
  if (broadcast.title_regex && broadcast.title_regex.regex.test(display_name(candidate))==broadcast.title_regex.invert) return false
  if (broadcast.input_regex && broadcast.input_regex.regex.test(candidate.label)==broadcast.input_regex.invert) return false
  return true
}

// Re-exported because ue_properties.js and floating_window.js import them and
// the conversion dropped them, which is a link error at load rather than a
// parse error — it passes every syntax check and takes the module down.

/** Builds a DOM element. Pure DOM; no host surface involved. */
export function create(tag, clss, parent, properties) {
  const nd = document.createElement(tag)
  if (clss) clss.split(' ').forEach((s) => nd.classList.add(s))
  if (parent) parent.appendChild(nd)
  if (properties) Object.assign(nd, properties)
  return nd
}

/** Whether a node is one of the pack's broadcast types. */
export function is_UEnode(node) {
  const type = node.comfyClass ?? node.type
  return !!type && UE_TYPES.test(type)
}

function version_compare(x,y) {
  if (x==y) return  0
  if (!y)   return  1
  if (!x)   return -1
  const xbits = x.split('.')
  const ybits = y.split('.')
  var result = 0
  for (var i=0; result==0 && i<Math.min(xbits.length, ybits.length); i++) {
    if (parseInt(xbits[i]) < parseInt(ybits[i])) result = -1
    if (parseInt(xbits[i]) > parseInt(ybits[i])) result = 1
  }
  if (result==0) {
    if (xbits.length < ybits.length) result = -1
    if (xbits.length > ybits.length) result = 1
  }
  return result
}

export function version_at_least(x,y) {
  return (version_compare(x,y) >= 0)
}

export function node_can_broadcast(node) {
  return !node.getProperty("ue_materialized") && (!!node.getProperty("ue_convert") || is_UEnode(node))
}

export function is_able_to_broadcast(node, output_name) {
  if (!node.getProperty("ue_convert")) return false
  const output = node.outputs.byName(output_name)
  if (!output) {
    Logger.log_error(`Can't find output ${output_name} on node ${node.getTitle()}`)
    return false
  }
  const properties = node.getProperty("ue_properties") || {}
  return !properties.output_not_broadcasting?.[output_name]
}

export function find_duplicate_broadcasted_types(node) {
  const types = node.getProperty("ue_convert")
    ? node.outputs.all()
        .filter((output)=>is_able_to_broadcast(node, output.name))
        .map((output)=>output.type)
    : node.inputs.all()
        .map((input)=>input.link()?.type)
        .filter((type)=>type !== undefined)
  const seen = new Set()
  const duplicated = new Set()
  types.forEach((type)=>{
    if (seen.has(type)) duplicated.add(type)
    seen.add(type)
  })
  return duplicated
}
