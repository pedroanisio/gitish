"""
Tests for brain.py message sending functionality.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestMessageCreation:
    """Test message file creation."""
    
    def test_save_message_creates_file(self, initialized_identity, brain_module, temp_repo):
        """save_message should create a JSON file."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Hello, world!"}
        )
        
        assert filepath.exists()
        assert filepath.suffix == ".json"
    
    def test_save_message_content(self, initialized_identity, brain_module, temp_repo):
        """save_message should save correct content."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Test message content"}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["type"] == "message"
        assert message["body"] == "Test message content"
        assert message["from"] == initialized_identity["short_name"]
        assert message["from_id"] == initialized_identity["full_id"]
        assert "ts" in message
    
    def test_save_message_creates_directory(self, initialized_identity, brain_module, temp_repo):
        """save_message should create user directory if needed."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Test"}
        )
        
        expected_dir = Path(".brain/messages") / initialized_identity["short_name"]
        assert expected_dir.exists()
        assert expected_dir.is_dir()
    
    def test_save_message_unique_filenames(self, initialized_identity, brain_module, temp_repo):
        """Multiple messages should have unique filenames."""
        filepath1 = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Message 1"}
        )
        
        # No sleep needed - microseconds in timestamp ensure uniqueness
        filepath2 = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Message 2"}
        )
        
        # Filenames include microseconds, so should be different
        assert filepath1 != filepath2
        assert filepath1.exists()
        assert filepath2.exists()


class TestMessageTypes:
    """Test different message types."""
    
    def test_message_type(self, initialized_identity, brain_module, temp_repo):
        """Regular message type should be 'message'."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Hello"}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["type"] == "message"
    
    def test_claim_type(self, initialized_identity, brain_module, temp_repo):
        """Claim message type should be 'claim'."""
        filepath = brain_module.save_message(
            initialized_identity,
            "claim",
            {"phase": 11}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["type"] == "claim"
        assert message["phase"] == 11
    
    def test_release_type(self, initialized_identity, brain_module, temp_repo):
        """Release message type should be 'release'."""
        filepath = brain_module.save_message(
            initialized_identity,
            "release",
            {"phase": 11, "reason": "blocked"}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["type"] == "release"
        assert message["reason"] == "blocked"
    
    def test_complete_type(self, initialized_identity, brain_module, temp_repo):
        """Complete message type should be 'complete'."""
        filepath = brain_module.save_message(
            initialized_identity,
            "complete",
            {"phase": 11, "pr": "#42"}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["type"] == "complete"
        assert message["pr"] == "#42"


class TestMessageTimestamps:
    """Test timestamp handling in messages."""
    
    def test_timestamp_is_iso_format(self, initialized_identity, brain_module, temp_repo):
        """Timestamps should be in ISO format."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Test"}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        ts = message["ts"]
        
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed is not None
    
    def test_timestamp_is_utc(self, initialized_identity, brain_module, temp_repo):
        """Timestamps should be in UTC timezone."""
        ts = brain_module.now_iso()
        
        # Should contain timezone info
        assert "+" in ts or "Z" in ts


class TestEventAppending:
    """Test events.jsonl appending."""
    
    def test_append_event_creates_file(self, brain_module, temp_repo):
        """append_event should create events.jsonl if missing."""
        brain_module.append_event({"type": "test", "data": "value"})
        
        events_file = Path(".brain/events.jsonl")
        assert events_file.exists()
    
    def test_append_event_adds_line(self, brain_module, temp_repo):
        """append_event should add a new line to events.jsonl."""
        brain_module.append_event({"type": "event1"})
        brain_module.append_event({"type": "event2"})
        brain_module.append_event({"type": "event3"})
        
        events_file = Path(".brain/events.jsonl")
        with open(events_file) as f:
            lines = f.readlines()
        
        assert len(lines) == 3
    
    def test_append_event_is_valid_json(self, brain_module, temp_repo):
        """Each line in events.jsonl should be valid JSON."""
        brain_module.append_event({"type": "test", "nested": {"key": "value"}})
        
        events_file = Path(".brain/events.jsonl")
        with open(events_file) as f:
            for line in f:
                event = json.loads(line)  # Should not raise
                assert "type" in event
    
    def test_append_event_preserves_order(self, brain_module, temp_repo):
        """Events should be appended in order."""
        for i in range(5):
            brain_module.append_event({"type": "test", "index": i})
        
        events_file = Path(".brain/events.jsonl")
        with open(events_file) as f:
            for i, line in enumerate(f):
                event = json.loads(line)
                assert event["index"] == i


class TestEmptyAndEdgeCases:
    """Test edge cases for messages."""
    
    def test_empty_message_body(self, initialized_identity, brain_module, temp_repo):
        """Empty message body should still create valid file."""
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": ""}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["body"] == ""
    
    def test_unicode_message_body(self, initialized_identity, brain_module, temp_repo):
        """Unicode characters should be preserved."""
        body = "Hello 世界 🌍 émoji"
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": body}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["body"] == body
    
    def test_long_message_body(self, initialized_identity, brain_module, temp_repo):
        """Long messages should be saved completely."""
        body = "x" * 10000
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": body}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert len(message["body"]) == 10000
    
    def test_special_chars_in_message(self, initialized_identity, brain_module, temp_repo):
        """Special characters should be escaped properly."""
        body = 'Test "quoted" and \\backslash and \n newline'
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": body}
        )
        
        with open(filepath) as f:
            message = json.load(f)
        
        assert message["body"] == body

