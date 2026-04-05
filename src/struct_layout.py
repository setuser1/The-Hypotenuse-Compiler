"""Struct layout computation with C11 padding analysis and cache optimization."""

from dataclasses import dataclass
from typing import Dict, List, Optional


TYPE_INFO = {
    "char": (1, 1),
    "short": (2, 2),
    "int": (4, 4),
    "long": (8, 8),
    "long long": (8, 8),
    "float": (4, 4),
    "double": (8, 8),
    "long double": (16, 16),
    "void*": (8, 8),
    "_Bool": (1, 1),
}


@dataclass
class FieldInfo:
    """Information about a single struct field."""

    name: str
    type: str
    offset: int
    size: int
    alignment: int
    padding_before: int


@dataclass
class StructLayout:
    """Complete layout information for a struct."""

    name: Optional[str]
    fields: List[FieldInfo]
    total_size: int
    alignment: int
    padding_bytes: int
    cache_efficiency: float


def alignment_of(type_str: str) -> int:
    """Return the natural alignment for a type."""
    type_str = type_str.strip()
    if type_str in TYPE_INFO:
        return TYPE_INFO[type_str][1]
    if type_str.startswith("_Bool"):
        return 1
    if type_str.startswith("char"):
        return 1
    if type_str.startswith("short"):
        return 2
    if type_str.startswith("int"):
        return 4
    if type_str.startswith("long"):
        if "long long" in type_str:
            return 8
        return 8
    if type_str.startswith("float"):
        return 4
    if type_str.startswith("double"):
        if "long double" in type_str:
            return 16
        return 8
    if type_str.startswith("void*"):
        return 8
    return 8


def size_of(type_str: str) -> int:
    """Return the size for a type string, handling arrays."""
    type_str = type_str.strip()
    if "[" in type_str:
        base_type, array_part = type_str.split("[", 1)
        base_size = size_of(base_type.strip())
        count_str = array_part.split("]")[0].strip()
        if count_str:
            return base_size * int(count_str)
        return base_size
    if type_str in TYPE_INFO:
        return TYPE_INFO[type_str][0]
    return 8


def compute_layout(struct_def, context=None) -> StructLayout:
    """Compute the memory layout for a struct definition."""
    struct_name = getattr(struct_def, "name", None) or getattr(struct_def, "tag", None)
    fields_def = getattr(struct_def, "fields", [])
    if fields_def is None:
        fields_def = []
    if not fields_def:
        return StructLayout(
            name=struct_name,
            fields=[],
            total_size=0,
            alignment=1,
            padding_bytes=0,
            cache_efficiency=100.0,
        )
    fields = []
    current_offset = 0
    max_alignment = 1
    total_padding = 0
    for field_def in fields_def:
        field_name = getattr(field_def, "name", None) or ""
        field_type = getattr(field_def, "type", None) or "int"
        if isinstance(field_type, list):
            field_type = " ".join(str(t) for t in field_type)
        else:
            field_type = str(field_type)
        alignment = alignment_of(field_type)
        size = size_of(field_type)
        if alignment > max_alignment:
            max_alignment = alignment
        padding = 0
        if current_offset % alignment != 0:
            padding = alignment - (current_offset % alignment)
            current_offset += padding
            total_padding += padding
        field_info = FieldInfo(
            name=field_name,
            type=field_type,
            offset=current_offset,
            size=size,
            alignment=alignment,
            padding_before=padding,
        )
        fields.append(field_info)
        current_offset += size
    if current_offset % max_alignment != 0:
        tail_padding = max_alignment - (current_offset % max_alignment)
        current_offset += tail_padding
        total_padding += tail_padding
    total_size = current_offset
    payload = sum(f.size for f in fields)
    efficiency = (payload / total_size * 100) if total_size > 0 else 100.0
    return StructLayout(
        name=struct_name,
        fields=fields,
        total_size=total_size,
        alignment=max_alignment,
        padding_bytes=total_padding,
        cache_efficiency=efficiency,
    )


def layout_report(layout: StructLayout) -> str:
    """Generate a human-readable layout report."""
    lines = []
    name_str = layout.name or "(anonymous)"
    lines.append(f"Struct: {name_str}")
    lines.append(f"Size: {layout.total_size} bytes")
    lines.append(f"Alignment: {layout.alignment}")
    lines.append(f"Padding: {layout.padding_bytes} bytes")
    lines.append(f"Cache efficiency: {layout.cache_efficiency:.1f}%")
    lines.append("")
    lines.append("Field offsets:")
    for field in layout.fields:
        pad_str = f" + {field.padding_before} pad" if field.padding_before > 0 else ""
        lines.append(
            f"  {field.name}: offset={field.offset}, size={field.size}, "
            f"align={field.alignment}{pad_str}"
        )
    return "\n".join(lines)


def cache_analysis(layout: StructLayout, line_size: int = 64) -> dict:
    """Analyze cache line utilization."""
    if not layout.fields:
        return {
            "utilization": 100.0,
            "wasted_bytes": 0,
            "fields_per_line": [],
            "suggestions": [],
        }
    fields_by_line = []
    current_line_end = 0
    for field in layout.fields:
        field_end = field.offset + field.size
        if field.offset >= current_line_end:
            fields_by_line.append([field])
            current_line_end = ((field.offset // line_size) + 1) * line_size
        else:
            fields_by_line[-1].append(field)
    total_wasted = 0
    for i, group in enumerate(fields_by_line):
        line_start = i * line_size
        line_end = line_start + line_size
        used_start = group[0].offset
        used_end = max(f.offset + f.size for f in group)
        if used_start > line_start:
            total_wasted += used_start - line_start
        if used_end < line_end:
            total_wasted += line_end - used_end
    total_payload = sum(f.size for f in layout.fields)
    utilization = (
        (total_payload / layout.total_size * 100) if layout.total_size > 0 else 100.0
    )
    suggestions = []
    if utilization < 70:
        suggestions.append(
            "Consider reordering fields by alignment (largest first) to reduce padding."
        )
    if layout.padding_bytes > layout.total_size * 0.2:
        suggestions.append(
            "High padding ratio. Consider restructuring or using #pragma pack."
        )
    if any(f.padding_before > 8 for f in layout.fields):
        suggestions.append(
            "Large internal padding detected. Check if field order can be optimized."
        )
    return {
        "utilization": utilization,
        "wasted_bytes": total_wasted,
        "fields_per_line": [len(group) for group in fields_by_line],
        "suggestions": suggestions,
    }


def suggest_reordering(fields: List[FieldInfo]) -> List[FieldInfo]:
    """Suggest field reordering for better cache density."""
    return sorted(fields, key=lambda f: (-f.alignment, -f.size))


def padding_report(layouts: Dict[str, StructLayout]) -> str:
    """Generate a padding analysis report for all structs."""
    lines = []
    lines.append("Padding Analysis Report")
    lines.append("=" * 50)
    lines.append("")
    sorted_layouts = sorted(
        layouts.items(), key=lambda x: x[1].padding_bytes, reverse=True
    )
    for name, layout in sorted_layouts:
        lines.append(f"{name or '(anonymous)'}:")
        lines.append(f"  Total size: {layout.total_size} bytes")
        lines.append(
            f"  Padding: {layout.padding_bytes} bytes ({layout.padding_bytes / layout.total_size * 100:.1f}%)"
            if layout.total_size > 0
            else "  Padding: 0 bytes"
        )
        lines.append(f"  Cache efficiency: {layout.cache_efficiency:.1f}%")
        analysis = cache_analysis(layout)
        if analysis["suggestions"]:
            lines.append("  Suggestions:")
            for suggestion in analysis["suggestions"]:
                lines.append(f"    - {suggestion}")
        lines.append("")
    return "\n".join(lines)
