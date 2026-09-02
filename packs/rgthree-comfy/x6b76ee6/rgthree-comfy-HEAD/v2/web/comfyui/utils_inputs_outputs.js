// FULLY CONVERTED — the file's one export, behaviour unchanged.
//
// Drops the trailing inputs nothing is wired to, so a node that grows an input as
// the last one fills does not accumulate empty slots. Any Switch and Context call
// it here; Power Puter and Dynamic Context are its other two callers upstream and
// are punted for unrelated reasons.
//
// `nameMatch` is kept although neither converted caller passes one: it is what
// stops Dynamic Context's trim from eating a trailing input the user named, and
// that distinction is unrecoverable once the argument is gone.
export function removeUnusedInputsFromEnd(node, minNumber = 1, nameMatch) {
    if (node.isDeleted)
        return;
    for (let i = node.inputs.length - 1; i >= minNumber; i--) {
        const input = node.inputs.at(i);
        if (!input)
            continue;
        if (!input.isConnected) {
            if (!nameMatch || nameMatch.test(input.name)) {
                node.inputs.remove(i);
            }
            continue;
        }
        break;
    }
}
