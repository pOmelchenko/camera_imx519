#!/usr/bin/env python3
"""Take a phase-guided one-shot IMX519 photograph with a CDAF fallback.

Requires the experimental Q6A CAMSS module exposing VC0/DT0x36 on RDI2.
This is a board bring-up command; libcamera's in-stream AF remains separate.
"""

import argparse
import json
from pathlib import Path
from statistics import median
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent


def run(command, log):
    with log.open("w") as output:
        completed = subprocess.run(command, cwd=HERE, stdout=output,
                                   stderr=subprocess.STDOUT, timeout=45, check=False)
    if completed.returncode:
        raise RuntimeError(f"{' '.join(map(str, command))}: exit {completed.returncode}; see {log}")


def sample(code, directory):
    directory.mkdir()
    command = ["python3", str(HERE / "focus.py"), str(code), "--",
               "timeout", "--signal=INT", "--kill-after=3s", "12s",
               str(HERE / "build/kernel-pdaf/capture-meta"), "/dev/video4",
               str(directory), "12"]
    run(command, directory / "capture.log")
    analysis = subprocess.run(
        ["python3", str(HERE / "kernel/analyze-phase.py"), str(directory), "--center"],
        cwd=HERE, text=True, capture_output=True, timeout=10, check=True)
    frames = json.loads(analysis.stdout)["frames"]
    if len(frames) != 12:
        raise ValueError(f"Only {len(frames)} phase frames at code {code}")
    qualified = [item for item in frames
                 if item["qualified_regions"] >= 8 and item["median_phase"] is not None]
    if len(qualified) < 8:
        raise ValueError(f"Only {len(qualified)} qualified phase frames at code {code}")
    phases = [item["median_phase"] for item in qualified]
    result = {"raw_code": code, "phase": median(phases),
              "phase_range": [min(phases), max(phases)],
              "qualified_frames": len(qualified),
              "qualified_regions_min": min(item["qualified_regions"] for item in qualified)}
    (directory / "phase-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def next_code(samples):
    last = samples[-1]
    phase = last["phase"]
    if len(samples) > 1:
        previous = samples[-2]
        delta_phase = phase - previous["phase"]
        delta_code = last["raw_code"] - previous["raw_code"]
        slope = delta_phase / delta_code if delta_code else 0
    else:
        slope = 0
    # The calibrated slope is a starting step. A measured local slope takes
    # over only when its direction and magnitude are physically plausible.
    if not 0.04 <= slope <= 0.4:
        slope = 0.14
    correction = max(-600, min(600, round(-phase / slope)))
    candidate = max(0, min(4095, last["raw_code"] + correction))
    if candidate == last["raw_code"]:
        raise ValueError("Phase correction cannot move the lens")
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-only", action="store_true",
                        help="verify the phase loop without capturing a color image")
    args = parser.parse_args()
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="snapshot-pdaf-", dir=artifacts))
    samples = []
    selected = None
    error = None
    try:
        run(["timeout", "--signal=INT", "--kill-after=3s", "12s",
             "bash", str(HERE / "cam.sh"), "-c",
             "/base/soc@0/cci@ac4b000/i2c-bus@1/camera@1a", "--stream",
             "role=raw,width=1920,height=1080", "--capture=2"],
            directory / "warmup.log")
        run(["bash", str(HERE / "kernel/prepare-phase.sh")],
            directory / "prepare.log")
        code = 2047
        for index in range(4):
            result = sample(code, directory / f"step-{index}-{code}")
            samples.append(result)
            print(f"code={code} phase={result['phase']} "
                  f"qualified={result['qualified_regions_min']}", flush=True)
            if abs(result["phase"]) <= 5:
                selected = code
                break
            code = next_code(samples)
        if selected is None:
            raise ValueError("Phase did not converge within four samples")
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired,
            subprocess.CalledProcessError) as exc:
        error = str(exc)

    output = {"method": "PDAF" if selected is not None else "CDAF fallback",
              "selected_raw_code": selected, "samples": samples, "phase_error": error}
    (directory / "result.json").write_text(json.dumps(output, indent=2) + "\n")
    print(f"Artifacts: {directory}", flush=True)
    if error:
        print(f"PDAF unavailable: {error}", flush=True)
    if args.phase_only:
        return 0 if selected is not None else 1
    if selected is None:
        command = ["bash", str(HERE / "snapshot-af.sh"), "auto"]
    else:
        command = ["bash", str(HERE / "snapshot.sh"), str(selected)]
    run(command, directory / "snapshot.log")
    print((directory / "snapshot.log").read_text().strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
