# ComfyUI-StringConcatenate

**更新日: 2026年10月13日**

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) 用カスタムノード。5つの文字列を改行で1つに結合します。

リポジトリ: [https://github.com/mckey-dev/ComfyUI-StringConcatenate](https://github.com/mckey-dev/ComfyUI-StringConcatenate)

## 機能

- `string_1` ～ `string_5` の5入力（複数行テキスト）
- 入力順に `\n`（改行）で結合
- **text** … 下流ノードへ渡す結合文字列
- **preview** … 同じ結合文字列（プレビュー用出力）
- ノード上のテキスト UI で結果を確認（`OUTPUT_NODE`）
- 出力ソケットを接続しなくても実行時エラーになりません

## インストール

1. ComfyUI の `custom_nodes` フォルダへ本リポジトリを配置します。

   ```text
   ComfyUI/custom_nodes/ComfyUI-StringConcatenate/
   ```

2. ComfyUI を再起動するか、カスタムノードの再読み込みを行います。

追加の Python 依存パッケージは不要です。

## 使い方

1. ノードメニュー **text** から **5文字列改行結合** を追加します。
2. 各入力に文字列を入力します（未使用の枠は空のままで構いません）。
3. **text** を CLIP Text Encode など文字列入力のあるノードへ接続します。
4. **preview** は接続しなくても問題ありません。必要なら Show Text 系ノードなどへ接続できます。

空の入力も1行分として扱われ、改行は残ります（例: `A` + 空 + `B` → `A\n\nB`）。

## ライセンス

MIT License（詳細は [LICENSE](LICENSE)）。
