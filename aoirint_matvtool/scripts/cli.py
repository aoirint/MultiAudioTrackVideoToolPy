
from datetime import timedelta
import logging
from math import floor
from pathlib import Path
import sys
from typing import Optional
from tqdm import tqdm
from pydantic import BaseModel

from aoirint_matvtool import config
from aoirint_matvtool.inputs import ffmpeg_get_input
from aoirint_matvtool.fps import ffmpeg_fps
from aoirint_matvtool.key_frames import FfmpegKeyFrameOutputLine, ffmpeg_key_frames
from aoirint_matvtool.slice import ffmpeg_slice
from aoirint_matvtool.crop_scale import ffmpeg_crop_scale
from aoirint_matvtool.find_image import FfmpegBlackframeOutputLine, ffmpeg_find_image_generator
from aoirint_matvtool.select_audio import ffmpeg_select_audio
from aoirint_matvtool.util import (
  parse_ffmpeg_time_unit_syntax,
)
from aoirint_matvtool.progress import iter_progress


def command_input(args):
  input_path = Path(args.input_path)
  print(ffmpeg_get_input(
    input_path=input_path,
  ))

def command_fps(args):
  input_path = Path(args.input_path)

  print(ffmpeg_fps(
    input_path=input_path,
  ).fps)

def command_key_frames(args):
  input_path = Path(args.input_path)

  for output in ffmpeg_key_frames(
    input_path=input_path,
  ):
    if isinstance(output, FfmpegKeyFrameOutputLine):
      print(f'{output.time:.06f}')

def command_slice(args):
  ss = args.ss
  to = args.to
  input_path = Path(args.input_path)
  output_path = Path(args.output_path)

  print(ffmpeg_slice(
    ss=ss,
    to=to,
    input_path=input_path,
    output_path=output_path,
  ))


def command_crop_scale(args):
  input_path = Path(args.input_path)
  crop = args.crop
  scale = args.scale
  video_codec = args.video_codec
  output_path = Path(args.output_path)

  print(ffmpeg_crop_scale(
    input_path=input_path,
    crop=crop,
    scale=scale,
    video_codec=video_codec,
    output_path=output_path,
  ))


def command_find_image(args):
  ss = args.ss
  to = args.to
  input_video_path = Path(args.input_video_path)
  input_video_crop = args.input_video_crop
  reference_image_path = Path(args.reference_image_path)
  reference_image_crop = args.reference_image_crop
  fps = args.fps
  blackframe_amount = args.blackframe_amount
  blackframe_threshold = args.blackframe_threshold
  output_interval = args.output_interval
  progress_type = args.progress_type

  # FPS
  input_video_fps = ffmpeg_fps(input_path=input_video_path).fps
  assert input_video_fps is not None, 'FPS info not found in the input video'

  # Time
  raw_start_time = parse_ffmpeg_time_unit_syntax(ss) if ss is not None else None
  raw_start_timedelta = raw_start_time.to_timedelta() if raw_start_time is not None else timedelta(seconds=0)
  # raw_end_time = parse_ffmpeg_time_unit_syntax(to) if to is not None else None

  # キーフレーム情報をもとにstart_timedeltaを補正
  start_timedelta = timedelta(seconds=0)
  for output in ffmpeg_key_frames(
    input_path=input_video_path,
  ):
    if isinstance(output, FfmpegKeyFrameOutputLine):
      next_key_frame_timedelta = timedelta(seconds=output.time)

      # raw_start_timedeltaより前のキーフレームを選択（-ssオプションの挙動）
      if raw_start_timedelta <= next_key_frame_timedelta:
        break

      start_timedelta = next_key_frame_timedelta

  # Common func
  def format_timedelta(td: timedelta) -> str:
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    microseconds = td.microseconds

    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{microseconds:06d}'

  prev_input_timedelta = timedelta(seconds=-output_interval)

  # Execute
  for output, pbar in iter_progress(
    iterable=ffmpeg_find_image_generator(
      input_video_ss=ss, # FIXME: キーフレーム情報をもとにstart_timedeltaを補正
      input_video_to=to,
      input_video_path=input_video_path,
      input_video_crop=input_video_crop,
      reference_image_path=reference_image_path,
      reference_image_crop=reference_image_crop,
      fps=fps,
      blackframe_amount=blackframe_amount,
      blackframe_threshold=blackframe_threshold,
    ),
    progress_type=progress_type,
  ):
    if isinstance(output, FfmpegBlackframeOutputLine):
      progress = output.progress

      if timedelta(seconds=output_interval) <= progress.current_timedelta - prev_input_timedelta:
        print(f'Output | Time {format_timedelta(progress.current_timedelta_as_input_video_scale)}, frame {progress.current_frame_as_input_video_scale} (Internal time {progress.internal_time_unit_syntax}, frame {progress.internal_frame})')
        prev_input_timedelta = progress.current_frame_as_input_video_scale


def command_audio(args):
  input_path = Path(args.input_path)

  inp = ffmpeg_get_input(
    input_path=input_path,
  )

  assert len(inp.streams) != 0
  stream = inp.streams[0]

  for track in stream.tracks:
    if track.type == 'Audio':
      metadata_title = next(filter(lambda metadata: metadata.key.lower() == 'title', track.metadatas), None)
      title = metadata_title.value if metadata_title else ''

      print(f'Audio Track {track.index}: {title}')


def command_select_audio(args):
  input_path = Path(args.input_path)
  audio_indexes = args.audio_index
  output_path = Path(args.output_path)

  print(ffmpeg_select_audio(
    input_path=input_path,
    audio_indexes=audio_indexes,
    output_path=output_path,
  ))


def main():
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('-l', '--log_level', type=int, default=logging.INFO)
  parser.add_argument('--ffmpeg_path', type=str, default=config.FFMPEG_PATH)
  parser.add_argument('--ffprobe_path', type=str, default=config.FFPROBE_PATH)

  subparsers = parser.add_subparsers()

  parser_input = subparsers.add_parser('input')
  parser_input.add_argument('-i', '--input_path', type=str, required=True)
  parser_input.set_defaults(handler=command_input)

  parser_fps = subparsers.add_parser('fps')
  parser_fps.add_argument('-i', '--input_path', type=str, required=True)
  parser_fps.set_defaults(handler=command_fps)

  parser_key_frames = subparsers.add_parser('key_frames')
  parser_key_frames.add_argument('-i', '--input_path', type=str, required=True)
  parser_key_frames.set_defaults(handler=command_key_frames)

  parser_slice = subparsers.add_parser('slice')
  parser_slice.add_argument('-ss', type=str, required=True)
  parser_slice.add_argument('-to', type=str, required=True)
  parser_slice.add_argument('-i', '--input_path', type=str, required=True)
  parser_slice.add_argument('output_path', type=str)
  parser_slice.set_defaults(handler=command_slice)

  parser_crop_scale = subparsers.add_parser('crop_scale')
  parser_crop_scale.add_argument('-i', '--input_path', type=str, required=True)
  parser_crop_scale.add_argument('--crop', type=str, required=False)
  parser_crop_scale.add_argument('--scale', type=str, required=False)
  parser_crop_scale.add_argument('-vcodec', '--video_codec', type=str, required=False)
  parser_crop_scale.add_argument('output_path', type=str)
  parser_crop_scale.set_defaults(handler=command_crop_scale)

  parser_find_image = subparsers.add_parser('find_image')
  parser_find_image.add_argument('-ss', type=str, required=False)
  parser_find_image.add_argument('-to', type=str, required=False)
  parser_find_image.add_argument('-i', '--input_video_path', type=str, required=True)
  parser_find_image.add_argument('-icrop', '--input_video_crop', type=str, required=False)
  parser_find_image.add_argument('-ref', '--reference_image_path', type=str, required=True)
  parser_find_image.add_argument('-refcrop', '--reference_image_crop', type=str, required=False)
  parser_find_image.add_argument('--fps', type=int, required=False)
  parser_find_image.add_argument('-ba', '--blackframe_amount', type=int, default=98)
  parser_find_image.add_argument('-bt', '--blackframe_threshold', type=int, default=32)
  parser_find_image.add_argument('-it', '--output_interval', type=float, default=0)
  parser_find_image.add_argument('-p', '--progress_type', type=str, choices=('tqdm', 'plain', 'none'), default='tqdm')
  parser_find_image.set_defaults(handler=command_find_image)

  parser_audio = subparsers.add_parser('audio')
  parser_audio.add_argument('-i', '--input_path', type=str, required=True)
  parser_audio.set_defaults(handler=command_audio)

  parser_select_audio = subparsers.add_parser('select_audio')
  parser_select_audio.add_argument('-i', '--input_path', type=str, required=True)
  parser_select_audio.add_argument('--audio_index', type=int, nargs='+', required=True)
  parser_select_audio.add_argument('output_path', type=str)
  parser_select_audio.set_defaults(handler=command_select_audio)

  args = parser.parse_args()

  log_level = args.log_level
  logging.basicConfig(
    level=log_level,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
  )

  config.FFMPEG_PATH = args.ffmpeg_path
  config.FFPROBE_PATH = args.ffprobe_path

  if hasattr(args, 'handler'):
    args.handler(args)
  else:
    parser.print_help()


if __name__ == '__main__':
  main()
