# -*- coding: utf-8 -*-

# KiroGate
# Based on kiro-openai-gateway by Jwadow (https://github.com/Jwadow/kiro-openai-gateway)
# Original Copyright (C) 2025 Jwadow
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Thinking tag parser for processing <thinking>...</thinking> tags in streaming responses.

Parses streaming text and separates thinking content from regular text content.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List


class SegmentType(Enum):
    """Type of text segment."""
    TEXT = "text"
    THINKING = "thinking"


@dataclass
class TextSegment:
    """A segment of parsed text."""
    type: SegmentType
    content: str


class KiroThinkingTagParser:
    """
    Parser for <thinking>...</thinking> tags in streaming text.
    
    Handles incremental parsing of text that may contain thinking tags,
    properly handling partial tags that span multiple chunks.
    """
    
    def __init__(self):
        """Initialize the parser."""
        self._buffer = ""
        self._is_thinking_mode = False
        self._thinking_start_tag = "<thinking>"
        self._thinking_end_tag = "</thinking>"
    
    @property
    def is_thinking_mode(self) -> bool:
        """Whether currently inside a thinking block."""
        return self._is_thinking_mode
    
    def push_and_parse(self, text: str) -> List[TextSegment]:
        """
        Push new text and parse it into segments.
        
        Args:
            text: New text to parse
            
        Returns:
            List of parsed segments
        """
        self._buffer += text
        return self._parse_buffer()
    
    def _parse_buffer(self) -> List[TextSegment]:
        """Parse the current buffer and return segments."""
        segments: List[TextSegment] = []
        
        while self._buffer:
            if self._is_thinking_mode:
                # Looking for end tag
                end_idx = self._buffer.find(self._thinking_end_tag)
                if end_idx != -1:
                    # Found end tag
                    thinking_content = self._buffer[:end_idx]
                    if thinking_content:
                        segments.append(TextSegment(
                            type=SegmentType.THINKING,
                            content=thinking_content
                        ))
                    self._buffer = self._buffer[end_idx + len(self._thinking_end_tag):]
                    self._is_thinking_mode = False
                else:
                    # Check if buffer might contain partial end tag
                    partial_match = self._check_partial_tag(self._buffer, self._thinking_end_tag)
                    if partial_match > 0:
                        # Keep potential partial tag in buffer
                        safe_content = self._buffer[:-partial_match]
                        if safe_content:
                            segments.append(TextSegment(
                                type=SegmentType.THINKING,
                                content=safe_content
                            ))
                        self._buffer = self._buffer[-partial_match:]
                    else:
                        # No partial match, emit all as thinking
                        segments.append(TextSegment(
                            type=SegmentType.THINKING,
                            content=self._buffer
                        ))
                        self._buffer = ""
                    break
            else:
                # Looking for start tag
                start_idx = self._buffer.find(self._thinking_start_tag)
                if start_idx != -1:
                    # Found start tag
                    if start_idx > 0:
                        text_content = self._buffer[:start_idx]
                        segments.append(TextSegment(
                            type=SegmentType.TEXT,
                            content=text_content
                        ))
                    self._buffer = self._buffer[start_idx + len(self._thinking_start_tag):]
                    self._is_thinking_mode = True
                else:
                    # Check if buffer might contain partial start tag
                    partial_match = self._check_partial_tag(self._buffer, self._thinking_start_tag)
                    if partial_match > 0:
                        # Keep potential partial tag in buffer
                        safe_content = self._buffer[:-partial_match]
                        if safe_content:
                            segments.append(TextSegment(
                                type=SegmentType.TEXT,
                                content=safe_content
                            ))
                        self._buffer = self._buffer[-partial_match:]
                    else:
                        # No partial match, emit all as text
                        segments.append(TextSegment(
                            type=SegmentType.TEXT,
                            content=self._buffer
                        ))
                        self._buffer = ""
                    break
        
        return segments
    
    def _check_partial_tag(self, text: str, tag: str) -> int:
        """
        Check if text ends with a partial match of tag.
        
        Returns the length of the partial match, or 0 if no partial match.
        """
        for i in range(1, len(tag)):
            if text.endswith(tag[:i]):
                return i
        return 0
    
    def flush(self) -> List[TextSegment]:
        """
        Flush any remaining content in the buffer.
        
        Call this when the stream ends to get any remaining content.
        
        Returns:
            List of remaining segments
        """
        segments: List[TextSegment] = []
        
        if self._buffer:
            segment_type = SegmentType.THINKING if self._is_thinking_mode else SegmentType.TEXT
            segments.append(TextSegment(
                type=segment_type,
                content=self._buffer
            ))
            self._buffer = ""
        
        return segments
    
    def reset(self) -> None:
        """Reset the parser state."""
        self._buffer = ""
        self._is_thinking_mode = False
