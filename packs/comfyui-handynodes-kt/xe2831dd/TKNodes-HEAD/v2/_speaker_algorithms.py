"""Pinned active speaker methods; workflow carrier supplied per execution."""
import json

class TKLocateSpeakersUsingSilenceBreaks:

    @classmethod
    def INPUT_TYPES(s):
        inputs = {'required': {'silence_threshold': ('FLOAT', {'default': 1.0, 'min': 0.2, 'max': 4.0, 'step': 0.01}), 'fullaudio': ('AUDIO',), 'duration': ('FLOAT', {'default': 0.0, 'min': 0.0}), 'track_start_1': ('FLOAT', {'default': 0.0, 'max': 500.0, 'hidden': True}), 'track_end_1': ('FLOAT', {'default': 0.0, 'max': 500.0, 'hidden': True})}, 'optional': {'speaker_times': ('STRING', {'default': '[]', 'hidden': True}), 'track_state': ('STRING', {'default': 'DataUnchanged', 'hidden': True})}}
        for i in range(2, 15):
            inputs['optional'][f'track_start_{i}'] = ('FLOAT', {'default': 0.0, 'max': 500.0, 'hidden': True})
            inputs['optional'][f'track_end_{i}'] = ('FLOAT', {'default': 0.0, 'max': 500.0, 'hidden': True})
        return inputs
    RETURN_TYPES = ('STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('diarization', 'speakersTrackInfo1', 'speakersTrackInfo2')
    FUNCTION = 'calculatTracksBySilence'
    CATEGORY = 'TKNodes'
    DESCRIPTION = 'This node locates speakers in an Audio file base on silence breaks.  Priarily this is use with AI generated audo.  Make sure you put breaks in audioi file for this to work.  Use the threshold to determine how much silence to insert'

    def calculatTracksBySilence(self, silence_threshold, fullaudio, duration, speaker_times='[]', track_state='DataUnchanged', **kwargs):
        waveform = fullaudio['waveform']
        sample_rate = fullaudio['sample_rate']
        computed_duration = waveform.shape[-1] / sample_rate
        manualDiarization = self.convertEditBoxesToDiarization(**kwargs)
        if track_state == 'DataChange':
            speaker_times = manualDiarization
            speaker1tracks, speaker2tracks = self.extact_2_speakers_from_diarization(manualDiarization)
        else:
            diarization = self.autoSegmentsFromAudio
            speaker_times = diarization
            speaker1tracks, speaker2tracks = self.extact_2_speakers_from_diarization(diarization)
        sp1 = self.convert_segments_to_track_string(speaker1tracks)
        sp2 = self.convert_segments_to_track_string(speaker2tracks)
        return {'ui': {'duration': [computed_duration], 'speaker_times': speaker_times}, 'result': (json.dumps(speaker_times), sp1, sp2)}

    def convertEditBoxesToDiarization(self, **kwargs):
        segments = []
        for i in range(1, 15):
            start = kwargs.get(f'track_start_{i}', 0.0)
            end = kwargs.get(f'track_end_{i}', 0.0)
            if end > start:
                speaker = 0 if i <= 7 else 1
                segments.append({'start': start, 'end': end, 'speaker': speaker})
        segments.sort(key=lambda x: x['start'])
        return segments

    def convert_segments_to_track_string(self, segments):
        """
        Converts a list of segment dictionaries into a flat string.
        Input: [{"start": 0.0, "end": 3.9, "speaker": 0}, ...]
        Output: "0.000,3.942,5.193,9.510"
        """
        if not segments:
            return ''
        parts = []
        for seg in segments:
            start = seg.get('start', 0.0)
            end = seg.get('end', 0.0)
            parts.append(f'{float(start):.3f}')
            parts.append(f'{float(end):.3f}')
        return ','.join(parts)

    def extact_2_speakers_from_diarization(self, diarData):
        speaker1Segs = []
        speaker2Segs = []
        for seg in diarData:
            if seg['speaker'] == 1:
                speaker2Segs.append(seg)
            else:
                speaker1Segs.append(seg)
        return (speaker1Segs, speaker2Segs)

    def merge_small_consecutive_segments(self, segments, max_duration=10.0):
        """
        Merges consecutive segments from the same speaker if they are small (< max_duration).
        
        Rules:
        - Scan for consecutive segments with the same speaker
        - If a segment is < max_duration, try to merge it with the next segment
        (same speaker) as long as the combined duration stays < max_duration
        - Once a merge would exceed max_duration, start a new merged segment
        
        Args:
            segments: List of dicts with 'start', 'end', 'speaker' keys
            max_duration: Maximum duration in seconds for merging (default: 10.0)
        
        Returns:
            List of merged segment dicts
        """
        if not segments:
            return []
        merged = []
        current = dict(segments[0])
        for next_seg in segments[1:]:
            same_speaker = next_seg['speaker'] == current['speaker']
            current_duration = current['end'] - current['start']
            combined_duration = next_seg['end'] - current['start']
            if same_speaker and current_duration < max_duration and (combined_duration < max_duration):
                current['end'] = next_seg['end']
            else:
                merged.append(current)
                current = dict(next_seg)
        merged.append(current)
        return merged

