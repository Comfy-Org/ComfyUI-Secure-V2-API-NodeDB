"""Music Prompt Pixaroma - the two measured formulas, verbatim.

GENERATED. Do not hand-edit: it is written by
`scripts/gen_music_formulas.py`, which lifts each string out of the probe file
that measured it (`_minimax_music3_formulas.py` for the caption,
`_minimax_music3_duration.py` for the round-three lyrics) with
`ast.literal_eval`. Retyping a measured formula is how a node quietly stops
being the thing that was measured.

The caption scored 6/6 on every axis first time. The lyrics took three rounds;
what is here is round three, which is dependable at the short end (20 runs of a
thirty second song all gave 8 sung lines in 2 sections). Both were measured on
`qwen3.5_4b_int8_convrot.safetensors` - the caption at temperature 0.3 and the
lyrics at 0.8, which is why this node runs two generations with DIFFERENT
sampling rather than one pass with one setting.

Full account: `.claude/patterns/music-prompt.md`.
"""

CAPTION_FORMULA = 'You write the STRUCTURED CAPTION that a music model reads to compose a song. Turn the idea below into that caption and write nothing else.\n\nWrite it as three short labelled parts, in this order, each on its own line.\n\nGlobal Metadata: name the genre and a subgenre, a BPM as a number, a key and scale, how the feeling moves from the start of the song to the end, where someone would listen to it, and how the recording should sound.\n\nVocal Details: say whether the voice is male or female, what the voice sounds like, how it is performed, and whether there are harmonies or backing vocals.\n\nArrangement: name the instruments that carry the song and the ones that support it, how the instruments change between sections, the groove, what the bass and the drums do, and how much space the recording has.\n\nChoose words that suit THIS idea. Where the idea already fixes something, such as a tempo or an instrument, keep it exactly and build the rest around it.\n\nNever write any lyrics, any section tag in square brackets, or any quoted words the singer would sing: this caption describes the SOUND, and the words are handed to the model separately. Do not use markdown, headings, bullet points or asterisks. Do not introduce your answer or repeat the idea back. Start with the words Global Metadata.'

LYRICS_FORMULA = 'You write the LYRICS a music model will sing. Turn the idea below into a song and write nothing else.\n\nLay it out with a section tag on its own line before each part, choosing from [Intro] [Verse] [Pre-Chorus] [Chorus] [Post-Chorus] [Bridge] [Instrumental] [Solo] [Outro].\n\nFIT THE WORDS TO THE LENGTH ASKED FOR. A sung line takes about three seconds, so a four line section runs about twelve. Count your lines against the time you are given and stop when you reach it, because anything past the end is simply cut off. Under forty seconds, write one verse and one chorus and nothing else. Around a minute, a verse, a chorus, a second verse and the chorus again. Around two minutes, add a bridge and a final chorus. Longer than that, add another verse or a solo. When the idea does not say how long, write the two minute shape.\n\nA section tag can stand completely alone with nothing written under it, and that means the band plays and nobody sings there. That is how you open with music or take a break, but it still uses up time, so only do it when there is room to spare. Only write a line under a tag when there are words to be sung.\n\nKeep the lines short enough to sing in one breath. Let the chorus repeat almost the same words each time, because that is what makes it a chorus. Write in the language the idea is written in.\n\nEvery line you write is words a voice will sing, including anything inside brackets or parentheses, so keep each line to something a singer would actually sing. The instruments, the tempo and the mood are described somewhere else and are not your job here. No markdown, no quotation marks around the lines, and no note explaining what you did. Start with a section tag.'
