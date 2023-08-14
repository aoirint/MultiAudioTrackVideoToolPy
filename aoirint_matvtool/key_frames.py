import re
import subprocess
from pathlib import Path
from typing import Generator

from pydantic import BaseModel

from . import config


class FfmpegKeyFrameOutputLine(BaseModel):
    time: float


def ffmpeg_key_frames(
    input_path: Path,
) -> Generator[FfmpegKeyFrameOutputLine, None, None]:
    command = [
        config.FFPROBE_PATH,
        "-hide_banner",
        "-skip_frame",
        "nokey",
        "-select_streams",
        "v",
        "-show_frames",
        "-show_entries",
        "frame=pkt_pts_time",
        "-of",
        "csv",
        str(input_path),
    ]

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        encoding="utf-8",
    )

    try:
        while proc.poll() is None:
            assert proc.stdout is not None
            line = proc.stdout.readline().rstrip()

            # Workaround for FFprobe issue: (side_data.+)?
            # https://trac.ffmpeg.org/ticket/7153
            # Correct: frame,0.007000,side_data,H.26[45] User Data Unregistered SEI message
            # Broken: frame,0.007000side_data,H.26[45] User Data Unregistered SEI message
            match = re.match(r"^frame,(.+?)(side_data.+)?$", line)
            # match = re.match(r"^frame,(.+)$", line)

            if match:  # frame,1.983000
                seconds = float(match.group(1).strip())
                output = FfmpegKeyFrameOutputLine(time=seconds)
                yield output

        result_code = proc.wait()
        if result_code != 0:
            raise Exception(f"FFmpeg errored. code {result_code}")
    finally:
        proc.kill()
