function getFromPngBuffer(buffer) {
    const pngData = new Uint8Array(buffer);
    const dataView = new DataView(pngData.buffer);
    if (dataView.getUint32(0) !== 0x89504e47) {
        console.error('Not a valid PNG file');
        return;
    }
    let offset = 8;
    let txt_chunks = {};
    while (offset < pngData.length) {
        const length = dataView.getUint32(offset);
        const type = String.fromCharCode(...pngData.slice(offset + 4, offset + 8));
        if (type === 'tEXt' || type == 'comf' || type === 'iTXt') {
            let keyword_end = offset + 8;
            while (pngData[keyword_end] !== 0) {
                keyword_end++;
            }
            const keyword = String.fromCharCode(...pngData.slice(offset + 8, keyword_end));
            const contentArraySegment = pngData.slice(keyword_end + 1, offset + 8 + length);
            const contentJson = new TextDecoder('utf-8').decode(contentArraySegment);
            txt_chunks[keyword] = contentJson;
        }
        offset += 12 + length;
    }
    return txt_chunks;
}
function getFromPngFile(file) {
    return new Promise((r) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            r(getFromPngBuffer(event.target.result));
        };
        reader.readAsArrayBuffer(file);
    });
}
function parseExifData(exifData) {
    const isLittleEndian = String.fromCharCode(...exifData.slice(0, 2)) === 'II';
    function readInt(offset, isLittleEndian, length) {
        let arr = exifData.slice(offset, offset + length);
        if (length === 2) {
            return new DataView(arr.buffer, arr.byteOffset, arr.byteLength).getUint16(0, isLittleEndian);
        }
        else if (length === 4) {
            return new DataView(arr.buffer, arr.byteOffset, arr.byteLength).getUint32(0, isLittleEndian);
        }
        throw new Error('Shouldn\'t get here.');
    }
    const ifdOffset = readInt(4, isLittleEndian, 4);
    function parseIFD(offset) {
        const numEntries = readInt(offset, isLittleEndian, 2);
        const result = {};
        for (let i = 0; i < numEntries; i++) {
            const entryOffset = offset + 2 + i * 12;
            const tag = readInt(entryOffset, isLittleEndian, 2);
            const type = readInt(entryOffset + 2, isLittleEndian, 2);
            const numValues = readInt(entryOffset + 4, isLittleEndian, 4);
            const valueOffset = readInt(entryOffset + 8, isLittleEndian, 4);
            let value;
            if (type === 2) {
                value = new TextDecoder('utf-8').decode(exifData.subarray(valueOffset, valueOffset + numValues - 1));
            }
            result[tag] = value;
        }
        return result;
    }
    const ifdData = parseIFD(ifdOffset);
    return ifdData;
}
function splitValues(input) {
    var output = {};
    for (var key in input) {
        var value = input[key];
        var splitValues = value.split(':', 2);
        output[splitValues[0]] = splitValues[1];
    }
    return output;
}
export function getPngMetadata(file) {
    return getFromPngFile(file);
}
export function getWebpMetadata(file) {
    return new Promise((r) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const webp = new Uint8Array(event.target.result);
            const dataView = new DataView(webp.buffer);
            if (dataView.getUint32(0) !== 0x52494646 ||
                dataView.getUint32(8) !== 0x57454250) {
                console.error('Not a valid WEBP file');
                r({});
                return;
            }
            let offset = 12;
            let txt_chunks = {};
            while (offset < webp.length) {
                const chunk_length = dataView.getUint32(offset + 4, true);
                const chunk_type = String.fromCharCode(...webp.slice(offset, offset + 4));
                if (chunk_type === 'EXIF') {
                    if (String.fromCharCode(...webp.slice(offset + 8, offset + 8 + 6)) ==
                        'Exif\0\0') {
                        offset += 6;
                    }
                    let data = parseExifData(webp.slice(offset + 8, offset + 8 + chunk_length));
                    for (var key in data) {
                        const value = data[key];
                        if (typeof value === 'string') {
                            const index = value.indexOf(':');
                            txt_chunks[value.slice(0, index)] = value.slice(index + 1);
                        }
                    }
                    break;
                }
                offset += 8 + chunk_length;
            }
            r(txt_chunks);
        };
        reader.readAsArrayBuffer(file);
    });
}
export function getLatentMetadata(file) {
    return new Promise((r) => {
        const reader = new FileReader();
        reader.onload = (event) => {
            const safetensorsData = new Uint8Array(event.target.result);
            const dataView = new DataView(safetensorsData.buffer);
            let header_size = dataView.getUint32(0, true);
            let offset = 8;
            let header = JSON.parse(new TextDecoder().decode(safetensorsData.slice(offset, offset + header_size)));
            r(header.__metadata__);
        };
        var slice = file.slice(0, 1024 * 1024 * 4);
        reader.readAsArrayBuffer(slice);
    });
}
// `importA1111` removed (250 lines). The three metadata readers above convert to nothing
// because they touch no ComfyUI API at all, and they are the live surface: comfyui_shim.js
// re-exports getPngMetadata/getWebpMetadata from here. `importA1111` is exported and
// imported by nothing — grep the pack and this declaration is its only mention — so it is
// unreachable code and dropping it costs no behaviour.
//
// DROPPED: `importA1111`. It builds a whole txt2img workflow from an A1111 parameter
// string: nine detached node constructions, `graph.clear()`, `graph.add()` per node,
// `node.connect()` between them, and `graph.arrange()` to lay the result out. The local
// `api` wrapper and its `rgthree_api.js` import went with it — that function was their
// only caller. Four things would be needed to bring it back, recorded here so a port does
// not have to rediscover them:
//
//   - `graph.clear()`. GraphHandle offers add/remove/duplicate but no "empty this
//     document"; emulating it as `nodes().forEach(remove)` is a guess about links,
//     reroutes and id state that nothing published confirms.
//   - `graph.arrange()`. There is no published auto-layout, so every imported node would
//     land on top of the next at the same position — which makes the import useless
//     rather than merely different.
//   - a writable graph other than the visible one. The function takes its target graph as
//     an argument; `comfy.graph` is the graph on screen and `comfy.graph.subgraphs()`
//     reaches the others only to read, so a converted body would silently ignore the
//     caller's choice of document.
//   - a rewrite rather than a translation for the construction order. `LiteGraph.createNode(type)`
//     builds a node *detached*, and this code makes nine, then calls `graph.clear()`, then
//     adds them; `comfy.graph.add(type)` creates and inserts in one step, so the clear
//     would destroy the nodes just made.
