from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ============================================================
# Raw motion contract
# ============================================================

@dataclass(frozen=True)
class RawJoint:
    name: str
    parent: Optional[str]
    offset: tuple[float, float, float]
    channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class RawJointTransform:
    translation: tuple[float, float, float]
    rotation_euler: tuple[float, float, float]
    rotation_order: tuple[str, ...] = ("X", "Y", "Z")


@dataclass(frozen=True)
class RawFrame:
    index: int
    timestamp: float
    joints: dict[str, RawJointTransform]


@dataclass(frozen=True)
class RawMotion:
    source_format: str
    frame_rate: float
    frame_count: int
    duration: float
    joints: tuple[RawJoint, ...]
    frames: tuple[RawFrame, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Exceptions
# ============================================================

class MotionParserError(Exception):
    """Base class for parser errors."""


class UnsupportedMotionFormat(MotionParserError):
    """Raised when a motion format is unsupported."""


class BVHParseError(MotionParserError):
    """Raised when a BVH file is invalid."""


class FBXParseError(MotionParserError):
    """Raised when an FBX file cannot be parsed."""


# ============================================================
# BVH
# ============================================================

class BVHParser:
    """
    Native deterministic BVH parser.

    BVH is intentionally parsed without a third-party library.
    """

    _POSITION_CHANNELS = {
        "Xposition",
        "Yposition",
        "Zposition",
    }

    _ROTATION_CHANNELS = {
        "Xrotation",
        "Yrotation",
        "Zrotation",
    }

    def parse(self, path: str | Path) -> RawMotion:
        source = Path(path)

        if not source.exists():
            raise FileNotFoundError(
                f"Motion file does not exist: {source}"
            )

        if not source.is_file():
            raise BVHParseError(
                f"Motion path is not a file: {source}"
            )

        if source.suffix.lower() != ".bvh":
            raise BVHParseError(
                f"Expected .bvh file, got {source.suffix}"
            )

        try:
            content = source.read_text(
                encoding="utf-8-sig"
            )
        except UnicodeDecodeError as exc:
            raise BVHParseError(
                f"Unable to decode BVH file: {source}"
            ) from exc

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip()
        ]

        joints, motion_index = self._parse_hierarchy(lines)

        frame_count, frame_time, values = (
            self._parse_motion(
                lines[motion_index:]
            )
        )

        frames = self._decode_frames(
            joints=joints,
            frame_count=frame_count,
            frame_time=frame_time,
            values=values,
        )

        return RawMotion(
            source_format="bvh",
            frame_rate=1.0 / frame_time,
            frame_count=frame_count,
            duration=(
                max(frame_count - 1, 0)
                * frame_time
            ),
            joints=tuple(
                RawJoint(
                    name=joint["name"],
                    parent=joint["parent"],
                    offset=tuple(joint["offset"]),
                    channels=tuple(joint["channels"]),
                )
                for joint in joints
            ),
            frames=tuple(frames),
            metadata={
                "source_file": source.name,
                "format": "BVH",
            },
        )

    def _parse_hierarchy(
        self,
        lines: list[str],
    ) -> tuple[list[dict[str, Any]], int]:

        if not lines:
            raise BVHParseError("BVH file is empty")

        if lines[0].upper() != "HIERARCHY":
            raise BVHParseError(
                "BVH must begin with HIERARCHY"
            )

        joints: list[dict[str, Any]] = []
        stack: list[dict[str, Any]] = []

        current: Optional[dict[str, Any]] = None
        motion_index: Optional[int] = None

        i = 1

        while i < len(lines):
            line = lines[i]
            parts = line.split()

            if line.upper() == "MOTION":
                motion_index = i + 1
                break

            if line == "{":
                i += 1
                continue

            if line == "}":
                if stack:
                    stack.pop()

                current = (
                    stack[-1]
                    if stack
                    else None
                )

                i += 1
                continue

            if not parts:
                i += 1
                continue

            keyword = parts[0].upper()

            if keyword in {"ROOT", "JOINT"}:
                if len(parts) != 2:
                    raise BVHParseError(
                        f"Invalid {keyword} declaration: "
                        f"{line}"
                    )

                name = parts[1]

                if any(
                    joint["name"] == name
                    for joint in joints
                ):
                    raise BVHParseError(
                        f"Duplicate joint name: {name}"
                    )

                parent = (
                    stack[-1]["name"]
                    if stack
                    else None
                )

                joint = {
                    "name": name,
                    "parent": parent,
                    "offset": [0.0, 0.0, 0.0],
                    "channels": [],
                }

                joints.append(joint)
                stack.append(joint)
                current = joint

            elif keyword == "OFFSET":
                if current is None:
                    raise BVHParseError(
                        "OFFSET encountered without "
                        "an active joint"
                    )

                if len(parts) != 4:
                    raise BVHParseError(
                        f"Invalid OFFSET declaration: "
                        f"{line}"
                    )

                try:
                    current["offset"] = [
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                    ]
                except ValueError as exc:
                    raise BVHParseError(
                        f"Invalid OFFSET values: {line}"
                    ) from exc

            elif keyword == "CHANNELS":
                if current is None:
                    raise BVHParseError(
                        "CHANNELS encountered without "
                        "an active joint"
                    )

                if len(parts) < 2:
                    raise BVHParseError(
                        f"Invalid CHANNELS declaration: "
                        f"{line}"
                    )

                try:
                    count = int(parts[1])
                except ValueError as exc:
                    raise BVHParseError(
                        f"Invalid channel count: {line}"
                    ) from exc

                channels = parts[2:]

                if len(channels) != count:
                    raise BVHParseError(
                        f"Joint '{current['name']}' declares "
                        f"{count} channels but has "
                        f"{len(channels)}"
                    )

                invalid = [
                    channel
                    for channel in channels
                    if (
                        channel
                        not in self._POSITION_CHANNELS
                        and channel
                        not in self._ROTATION_CHANNELS
                    )
                ]

                if invalid:
                    raise BVHParseError(
                        f"Unsupported BVH channels "
                        f"for '{current['name']}': "
                        f"{invalid}"
                    )

                current["channels"] = channels

            elif keyword == "END":
                # End Site is structural information.
                pass

            i += 1

        if motion_index is None:
            raise BVHParseError(
                "BVH is missing MOTION section"
            )

        if not joints:
            raise BVHParseError(
                "BVH contains no joints"
            )

        roots = [
            joint
            for joint in joints
            if joint["parent"] is None
        ]

        if len(roots) != 1:
            raise BVHParseError(
                f"BVH must contain exactly one root; "
                f"found {len(roots)}"
            )

        return joints, motion_index

    def _parse_motion(
        self,
        lines: list[str],
    ) -> tuple[int, float, list[list[float]]]:

        frame_count: Optional[int] = None
        frame_time: Optional[float] = None

        values: list[list[float]] = []

        for line in lines:
            lower = line.lower()

            if lower.startswith("frames:"):
                try:
                    frame_count = int(
                        line.split(":", 1)[1].strip()
                    )
                except ValueError as exc:
                    raise BVHParseError(
                        f"Invalid frame count: {line}"
                    ) from exc

            elif lower.startswith("frame time:"):
                try:
                    frame_time = float(
                        line.split(":", 1)[1].strip()
                    )
                except ValueError as exc:
                    raise BVHParseError(
                        f"Invalid frame time: {line}"
                    ) from exc

            elif (
                frame_count is not None
                and frame_time is not None
            ):
                try:
                    values.append(
                        [
                            float(value)
                            for value in line.split()
                        ]
                    )
                except ValueError as exc:
                    raise BVHParseError(
                        f"Invalid motion data: {line}"
                    ) from exc

        if frame_count is None:
            raise BVHParseError(
                "Missing Frames declaration"
            )

        if frame_time is None:
            raise BVHParseError(
                "Missing Frame Time declaration"
            )

        if frame_count < 0:
            raise BVHParseError(
                "Frame count cannot be negative"
            )

        if frame_time <= 0:
            raise BVHParseError(
                "Frame Time must be greater than zero"
            )

        if len(values) != frame_count:
            raise BVHParseError(
                f"Expected {frame_count} frames, "
                f"received {len(values)}"
            )

        return frame_count, frame_time, values

    def _decode_frames(
        self,
        joints: list[dict[str, Any]],
        frame_count: int,
        frame_time: float,
        values: list[list[float]],
    ) -> list[RawFrame]:

        channel_count = sum(
            len(joint["channels"])
            for joint in joints
        )

        frames: list[RawFrame] = []

        for frame_index in range(frame_count):
            row = values[frame_index]

            if len(row) != channel_count:
                raise BVHParseError(
                    f"Frame {frame_index}: expected "
                    f"{channel_count} channel values, "
                    f"received {len(row)}"
                )

            cursor = 0
            frame_joints: dict[
                str,
                RawJointTransform,
            ] = {}

            for joint in joints:
                translation = [0.0, 0.0, 0.0]
                rotation = [0.0, 0.0, 0.0]
                rotation_order: list[str] = []

                for channel in joint["channels"]:
                    value = row[cursor]
                    cursor += 1

                    if channel == "Xposition":
                        translation[0] = value

                    elif channel == "Yposition":
                        translation[1] = value

                    elif channel == "Zposition":
                        translation[2] = value

                    elif channel == "Xrotation":
                        rotation[0] = value
                        rotation_order.append("X")

                    elif channel == "Yrotation":
                        rotation[1] = value
                        rotation_order.append("Y")

                    elif channel == "Zrotation":
                        rotation[2] = value
                        rotation_order.append("Z")

                    else:
                        raise BVHParseError(
                            f"Unsupported channel: {channel}"
                        )

                frame_joints[joint["name"]] = (
                    RawJointTransform(
                        translation=tuple(
                            translation
                        ),
                        rotation_euler=tuple(
                            rotation
                        ),
                        rotation_order=tuple(
                            rotation_order
                        ),
                    )
                )

            frames.append(
                RawFrame(
                    index=frame_index,
                    timestamp=(
                        frame_index * frame_time
                    ),
                    joints=frame_joints,
                )
            )

        return frames


# ============================================================
# FBX
# ============================================================

class FBXParser:
    """
    Autodesk FBX SDK adapter.

    The SDK performs FBX-specific scene and transform
    evaluation. The returned data is deliberately converted
    into our RawMotion contract immediately.
    """

    def __init__(
        self,
        sample_rate: Optional[float] = None,
        animation_stack: Optional[str] = None,
    ):
        self.sample_rate = sample_rate
        self.animation_stack_name = (
            animation_stack
        )

    @staticmethod
    def _load_sdk():
        try:
            import fbx
        except ImportError as exc:
            raise FBXParseError(
                "Autodesk FBX Python SDK is required "
                "for FBX parsing."
            ) from exc

        return fbx

    def parse(self, path: str | Path) -> RawMotion:
        source = Path(path)

        if not source.exists():
            raise FileNotFoundError(source)

        if not source.is_file():
            raise FBXParseError(
                f"FBX path is not a file: {source}"
            )

        if source.suffix.lower() != ".fbx":
            raise FBXParseError(
                f"Expected .fbx file, got "
                f"{source.suffix}"
            )

        fbx = self._load_sdk()

        manager = fbx.FbxManager.Create()

        if manager is None:
            raise FBXParseError(
                "Unable to create FBX manager"
            )

        try:
            io_settings = fbx.FbxIOSettings.Create(
                manager,
                fbx.IOSROOT,
            )

            manager.SetIOSettings(
                io_settings
            )

            scene = fbx.FbxScene.Create(
                manager,
                "MotionScene",
            )

            if scene is None:
                raise FBXParseError(
                    "Unable to create FBX scene"
                )

            self._import(
                fbx,
                manager,
                scene,
                source,
            )

            skeleton_nodes = (
                self._find_skeleton_nodes(
                    fbx,
                    scene,
                )
            )

            if not skeleton_nodes:
                raise FBXParseError(
                    "FBX contains no skeleton"
                )

            joints = self._extract_joints(
                skeleton_nodes
            )

            stack = (
                self._select_animation_stack(
                    fbx,
                    scene,
                )
            )

            if stack is None:
                raise FBXParseError(
                    "FBX contains no animation stack"
                )

            frames, frame_rate = (
                self._sample_animation(
                    fbx,
                    scene,
                    skeleton_nodes,
                    stack,
                )
            )

            return RawMotion(
                source_format="fbx",
                frame_rate=frame_rate,
                frame_count=len(frames),
                duration=(
                    frames[-1].timestamp
                    if frames
                    else 0.0
                ),
                joints=tuple(joints),
                frames=tuple(frames),
                metadata={
                    "source_file": source.name,
                    "format": "FBX",
                    "animation_stack": (
                        stack.GetName()
                    ),
                },
            )

        finally:
            manager.Destroy()

    def _import(
        self,
        fbx,
        manager,
        scene,
        path: Path,
    ) -> None:

        importer = fbx.FbxImporter.Create(
            manager,
            "MotionImporter",
        )

        if importer is None:
            raise FBXParseError(
                "Unable to create FBX importer"
            )

        try:
            initialized = importer.Initialize(
                str(path),
                -1,
                manager.GetIOSettings(),
            )

            if not initialized:
                error = (
                    importer
                    .GetStatus()
                    .GetErrorString()
                )

                raise FBXParseError(
                    f"FBX initialization failed: "
                    f"{error}"
                )

            if not importer.Import(scene):
                error = (
                    importer
                    .GetStatus()
                    .GetErrorString()
                )

                raise FBXParseError(
                    f"FBX import failed: {error}"
                )

        finally:
            importer.Destroy()

    def _find_skeleton_nodes(
        self,
        fbx,
        scene,
    ) -> list:

        result = []

        root = scene.GetRootNode()

        if root is None:
            return result

        def visit(node):
            attribute = (
                node.GetNodeAttribute()
            )

            if attribute is not None:
                if (
                    attribute.GetAttributeType()
                    == fbx.FbxNodeAttribute.eSkeleton
                ):
                    result.append(node)

            for index in range(
                node.GetChildCount()
            ):
                visit(node.GetChild(index))

        visit(root)

        return result

    def _extract_joints(
        self,
        skeleton_nodes: list,
    ) -> list[RawJoint]:

        skeleton_ids = {
            id(node)
            for node in skeleton_nodes
        }

        result = []

        for node in skeleton_nodes:
            parent = node.GetParent()
            parent_name = None

            while parent is not None:
                if id(parent) in skeleton_ids:
                    parent_name = (
                        parent.GetName()
                    )
                    break

                parent = parent.GetParent()

            offset = node.LclTranslation.Get()

            result.append(
                RawJoint(
                    name=node.GetName(),
                    parent=parent_name,
                    offset=(
                        float(offset[0]),
                        float(offset[1]),
                        float(offset[2]),
                    ),
                    channels=(
                        "translation",
                        "rotation",
                    ),
                )
            )

        return result

    def _select_animation_stack(
        self,
        fbx,
        scene,
    ):

        criteria = (
            fbx.FbxCriteria.ObjectType(
                fbx.FbxAnimStack.ClassId
            )
        )

        count = scene.GetSrcObjectCount(
            criteria
        )

        if count == 0:
            return None

        stacks = [
            scene.GetSrcObject(
                criteria,
                index,
            )
            for index in range(count)
        ]

        if self.animation_stack_name:
            for stack in stacks:
                if (
                    stack.GetName()
                    == self.animation_stack_name
                ):
                    return stack

            raise FBXParseError(
                f"Animation stack not found: "
                f"{self.animation_stack_name}"
            )

        return stacks[0]

    def _sample_animation(
        self,
        fbx,
        scene,
        skeleton_nodes: list,
        stack,
    ) -> tuple[list[RawFrame], float]:

        scene.SetCurrentAnimationStack(
            stack
        )

        time_span = stack.GetLocalTimeSpan()

        start = time_span.GetStart()
        stop = time_span.GetStop()

        frame_rate = float(
            self.sample_rate
            if self.sample_rate is not None
            else fbx.FbxTime.GetFrameRate(
                fbx.FbxTime.eDefaultMode
            )
        )

        if frame_rate <= 0:
            raise FBXParseError(
                "Sample rate must be greater than zero"
            )

        start_seconds = (
            start.GetSecondDouble()
        )

        stop_seconds = (
            stop.GetSecondDouble()
        )

        if stop_seconds < start_seconds:
            raise FBXParseError(
                "Invalid FBX animation time span"
            )

        duration = (
            stop_seconds - start_seconds
        )

        frame_count = (
            int(
                math.ceil(
                    duration * frame_rate
                )
            )
            + 1
        )

        frames = []

        for frame_index in range(frame_count):
            relative_time = (
                frame_index / frame_rate
            )

            absolute_time = (
                start_seconds
                + relative_time
            )

            if absolute_time > stop_seconds:
                absolute_time = stop_seconds

            time = fbx.FbxTime()
            time.SetSecondDouble(
                absolute_time
            )

            frame_joints = {}

            for node in skeleton_nodes:
                # Critical: local transform, not global.
                matrix = (
                    node.EvaluateLocalTransform(
                        time
                    )
                )

                translation = matrix.GetT()
                rotation = matrix.GetR()

                frame_joints[node.GetName()] = (
                    RawJointTransform(
                        translation=(
                            float(translation[0]),
                            float(translation[1]),
                            float(translation[2]),
                        ),
                        rotation_euler=(
                            float(rotation[0]),
                            float(rotation[1]),
                            float(rotation[2]),
                        ),
                        rotation_order=(
                            self._get_rotation_order(
                                fbx,
                                node,
                            )
                        ),
                    )
                )

            frames.append(
                RawFrame(
                    index=frame_index,
                    timestamp=round(
                        relative_time,
                        12,
                    ),
                    joints=frame_joints,
                )
            )

        return frames, frame_rate

    @staticmethod
    def _get_rotation_order(
        fbx,
        node,
    ) -> tuple[str, str, str]:

        order = node.GetRotationOrder(
            fbx.FbxNode.eSourcePivot
        )

        mapping = {
            fbx.FbxEuler.eOrderXYZ: (
                "X",
                "Y",
                "Z",
            ),
            fbx.FbxEuler.eOrderXZY: (
                "X",
                "Z",
                "Y",
            ),
            fbx.FbxEuler.eOrderYZX: (
                "Y",
                "Z",
                "X",
            ),
            fbx.FbxEuler.eOrderYXZ: (
                "Y",
                "X",
                "Z",
            ),
            fbx.FbxEuler.eOrderZXY: (
                "Z",
                "X",
                "Y",
            ),
            fbx.FbxEuler.eOrderZYX: (
                "Z",
                "Y",
                "X",
            ),
        }

        return mapping.get(
            order,
            ("X", "Y", "Z"),
        )


# ============================================================
# Unified parser
# ============================================================

class MotionParser:
    """
    Public parser entry point.
    """

    def __init__(
        self,
        sample_rate: Optional[float] = None,
        animation_stack: Optional[str] = None,
    ):
        self._bvh = BVHParser()

        self._fbx = FBXParser(
            sample_rate=sample_rate,
            animation_stack=animation_stack,
        )

    def parse(
        self,
        path: str | Path,
    ) -> RawMotion:

        path = Path(path)

        suffix = path.suffix.lower()

        if suffix == ".bvh":
            return self._bvh.parse(path)

        if suffix == ".fbx":
            return self._fbx.parse(path)

        raise UnsupportedMotionFormat(
            f"Unsupported motion format: "
            f"{suffix or '<none>'}"
        )