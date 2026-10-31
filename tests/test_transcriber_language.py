"""faster-whisper 语言码处理回归测试

CLI 默认 `--language auto`，而 faster-whisper 只接受具体语言码，
"auto" 会抛 ValueError: 'auto' is not a valid language code，
导致本地转写必然失败、双 ASR 校正永远走不通。自动检测需传 None。
"""
from unittest.mock import MagicMock, patch

from vidknot.core.transcriber import FasterWhisperASR


def _make_asr_and_model():
    asr = FasterWhisperASR()
    segment = MagicMock()
    segment.start = 0.0
    segment.end = 3.4
    segment.text = "大家好"
    model = MagicMock()
    model.transcribe.return_value = ([segment], None)
    return asr, model


def _transcribe(asr, model, language):
    with patch("faster_whisper.WhisperModel", return_value=model):
        with patch.object(
            FasterWhisperASR, "_validate_audio", return_value=None
        ):
            with patch.object(
                FasterWhisperASR, "_get_config",
                return_value={"model": "small", "device": "cpu", "compute_type": "int8",
                              "beam_size": 5, "vad_filter": True},
            ):
                return asr.transcribe("fake.mp3", language=language)


class TestFasterWhisperLanguage:
    def test_auto_becomes_none(self):
        """auto 必须转成 None，交给 faster-whisper 自动检测"""
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, "auto")
        assert model.transcribe.call_args.kwargs["language"] is None

    def test_auto_case_insensitive_and_whitespace(self):
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, " AUTO ")
        assert model.transcribe.call_args.kwargs["language"] is None

    def test_empty_language_becomes_none(self):
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, "")
        assert model.transcribe.call_args.kwargs["language"] is None

    def test_explicit_language_is_kept(self):
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, "zh")
        assert model.transcribe.call_args.kwargs["language"] == "zh"

    def test_explicit_language_is_stripped(self):
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, " en ")
        assert model.transcribe.call_args.kwargs["language"] == "en"

    def test_none_language_stays_none(self):
        asr, model = _make_asr_and_model()
        _transcribe(asr, model, None)
        assert model.transcribe.call_args.kwargs["language"] is None
