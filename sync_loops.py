#!/usr/bin/env python3
# sync_loops.py — combine a looping audio file and a looping video file into a single output.
# Repeats each to reach a minimum length, then adds optional audio fade in/out.
# Usage: ./sync_loops.py audio.mp3 video.mp4 output.mp4 [--min-length 30] [--fadeout 0.7] [--fadein 0.0]
#
# Requires: pip install moviepy   +   ffmpeg on PATH

import argparse
import os
import sys

from moviepy import VideoFileClip, AudioFileClip, concatenate_audioclips, concatenate_videoclips
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut


def sync_loops(audio_path, video_path, output_path, min_length=30.0, fadeout=0.7, fadein=0.0):
    print("Loading files...")
    audio_clip = AudioFileClip(audio_path)
    video_clip = VideoFileClip(video_path)

    audio_dur = audio_clip.duration
    video_dur = video_clip.duration

    # Round up to a whole number of audio loops that meets min_length.
    min_length = (max(1, min_length // audio_dur) + fadeout) * audio_dur

    print(f"Audio: {audio_dur:.3f}s  Video: {video_dur:.3f}s  Target: {min_length:.3f}s")

    video_repeats = max(1, -(-int(min_length) // int(video_dur)))  # ceiling div
    master_dur = video_repeats * video_dur
    print(f"Repeating video {video_repeats}x -> {master_dur:.3f}s")

    video_no_audio = video_clip.without_audio()
    final_video = concatenate_videoclips([video_no_audio] * video_repeats)

    audio_repeats = max(1, -(-int(master_dur) // int(audio_dur)))
    print(f"Repeating audio {audio_repeats}x")
    extended_audio = concatenate_audioclips([audio_clip] * audio_repeats).subclipped(0, master_dur)

    final_video.audio = extended_audio

    if fadein > 0:
        final_video = final_video.with_effects([AudioFadeIn(fadein * audio_dur)])
    if fadeout > 0:
        final_video = final_video.with_effects([AudioFadeOut(fadeout * audio_dur)])

    print(f"Exporting to {output_path}...")
    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
    )

    audio_clip.close()
    video_clip.close()
    return master_dur


def main():
    parser = argparse.ArgumentParser(
        description="Loop audio and video clips together to a minimum length."
    )
    parser.add_argument("audio", help="Audio file (e.g. loop.mp3)")
    parser.add_argument("video", help="Video file (e.g. loop.mp4)")
    parser.add_argument("output", help="Output file path")
    parser.add_argument("--min-length", type=float, default=30.0,
                        help="Minimum output duration in seconds (default: 30)")
    parser.add_argument("--fadeout", type=float, default=0.7,
                        help="Fade-out length as a fraction of one audio loop (default: 0.7)")
    parser.add_argument("--fadein", type=float, default=0.0,
                        help="Fade-in length as a fraction of one audio loop (default: 0.0)")
    args = parser.parse_args()

    for path, label in [(args.audio, "Audio"), (args.video, "Video")]:
        if not os.path.exists(path):
            print(f"Error: {label} file '{path}' not found", file=sys.stderr)
            sys.exit(1)

    if args.min_length <= 0:
        print("Error: --min-length must be positive", file=sys.stderr)
        sys.exit(1)

    try:
        dur = sync_loops(args.audio, args.video, args.output, args.min_length, args.fadeout, args.fadein)
        print(f"Done. Output: {args.output} ({dur:.3f}s)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
