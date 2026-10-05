# ComfyUI-AnimaPromptFormatter

[中文版](./README_zh.md) | Inglés

Un nodo personalizado de ComfyUI para formatear prompts de [Anima](https://huggingface.co/circlestone-labs/Anima).

A diferencia de los modelos SDXL como IllustrousXL o NoobAI XL, [Anima es sensible a los espacios en blanco, las comas y los saltos de línea](https://huggingface.co/circlestone-labs/Anima/discussions/57#6997ae1d9ab163d4a7a5121e). He creado este nodo personalizado para poder mantener mis hábitos de prompting de los modelos NoobAI.

## Reglas de Formateo

1. Elimina todos los saltos de línea (`\n`, `\r`)
2. Asegura exactamente un espacio después de cada coma
3. Elimina los espacios antes de las comas
4. Filtra etiquetas vacías provenientes de comas consecutivas

Ejemplo

**Entrada**:
```
tag1,tag2,  tag3
,tag4,,tag5
```

**Salida**:
```
tag1, tag2, tag3, tag4, tag5
```

## Uso
Es simplemente un nodo de entrada de cadena (string), conecta la salida a un nodo CLIPTextEncode y funcionará.
