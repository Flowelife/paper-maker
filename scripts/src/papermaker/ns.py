"""OOXML namespace constants and qualified-name helpers."""

from __future__ import annotations

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
XML = "http://www.w3.org/XML/1998/namespace"
V = "urn:schemas-microsoft-com:vml"
O = "urn:schemas-microsoft-com:office:office"
W10 = "urn:schemas-microsoft-com:office:word"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
WPG = "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
WP14 = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_BASE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

CONTENT_WIDTH_TWIPS = 8786
PAGE_WIDTH_TWIPS = 11906
PAGE_HEIGHT_TWIPS = 16838
MARGIN_TWIPS = 1418
GUTTER_TWIPS = 284


def w(tag: str) -> str:
    return "{%s}%s" % (W, tag)


def r(tag: str) -> str:
    return "{%s}%s" % (R, tag)


def m(tag: str) -> str:
    return "{%s}%s" % (M, tag)


def wp(tag: str) -> str:
    return "{%s}%s" % (WP, tag)


def a(tag: str) -> str:
    return "{%s}%s" % (A, tag)


def pic(tag: str) -> str:
    return "{%s}%s" % (PIC, tag)


def xml_space() -> str:
    return "{%s}space" % XML


def register_namespaces() -> None:
    from xml.etree.ElementTree import register_namespace

    register_namespace("w", W)
    register_namespace("r", R)
    register_namespace("m", M)
    register_namespace("wp", WP)
    register_namespace("a", A)
    register_namespace("pic", PIC)
    register_namespace("v", V)
    register_namespace("o", O)
    register_namespace("w10", W10)
    register_namespace("mc", MC)
    register_namespace("wps", WPS)
    register_namespace("wpg", WPG)
    register_namespace("wp14", WP14)
    register_namespace("w14", W14)
