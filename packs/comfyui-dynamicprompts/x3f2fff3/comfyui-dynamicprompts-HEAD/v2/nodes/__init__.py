# Secure Nodes V2: the original imported all six node modules here and built the node mappings.
# A guest cannot import magicprompt.py, because it imports transformers at module import. So this
# package init imports nothing. The secure entry (../_secure_dp.py) imports the node modules it runs
# and defines the same node ids and display names.
