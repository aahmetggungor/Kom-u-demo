package org.firatech.komsu

import android.Manifest
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.annotation.RequiresPermission
import java.io.ByteArrayOutputStream
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlin.math.sqrt
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async

data class CapturedAudio(val wav: ByteArray, val durationMs: Int)

object PcmWav {
    const val sampleRate = 16_000
    const val maxSeconds = 30
    const val maxPcmBytes = sampleRate * 2 * maxSeconds

    fun encode(pcm: ByteArray): CapturedAudio {
        require(pcm.size in 6_400..maxPcmBytes && pcm.size % 2 == 0)
        requireSpeechEnergy(pcm)
        val output = ByteArrayOutputStream(44 + pcm.size)
        fun text(value: String) = output.write(value.toByteArray(Charsets.US_ASCII))
        fun little(value: Int, bytes: Int) = repeat(bytes) { output.write(value ushr (8 * it)) }
        text("RIFF"); little(36 + pcm.size, 4); text("WAVEfmt "); little(16, 4)
        little(1, 2); little(1, 2); little(sampleRate, 4); little(sampleRate * 2, 4)
        little(2, 2); little(16, 2); text("data"); little(pcm.size, 4); output.write(pcm)
        return CapturedAudio(output.toByteArray(), (pcm.size * 1000.0 / (sampleRate * 2)).roundToInt())
    }

    fun validate(wav: ByteArray): Int {
        require(wav.size in (44 + 6_400)..(44 + maxPcmBytes))
        require(String(wav, 0, 4, Charsets.US_ASCII) == "RIFF")
        require(String(wav, 8, 4, Charsets.US_ASCII) == "WAVE")
        fun value(offset: Int, bytes: Int): Int =
            (0 until bytes).fold(0) { total, index -> total or ((wav[offset + index].toInt() and 0xff) shl (8 * index)) }
        require(value(20, 2) == 1 && value(22, 2) == 1)
        require(value(24, 4) == sampleRate && value(34, 2) == 16)
        require(String(wav, 36, 4, Charsets.US_ASCII) == "data")
        val pcmBytes = value(40, 4)
        require(pcmBytes == wav.size - 44 && pcmBytes <= maxPcmBytes)
        requireSpeechEnergy(wav.copyOfRange(44, wav.size))
        return (pcmBytes * 1000.0 / (sampleRate * 2)).roundToInt()
    }

    private fun requireSpeechEnergy(pcm: ByteArray) {
        var squares = 0.0
        var peak = 0
        var offset = 0
        while (offset < pcm.size) {
            val sample = (pcm[offset].toInt() and 0xff) or (pcm[offset + 1].toInt() shl 8)
            val signed = sample.toShort().toInt()
            squares += signed.toDouble() * signed
            peak = maxOf(peak, abs(signed))
            offset += 2
        }
        val rms = sqrt(squares / (pcm.size / 2)) / 32768.0
        require(rms >= 0.003 && peak / 32768.0 >= 0.01)
    }
}

class PcmRecorder {
    @Volatile private var recording = false
    private var audioRecord: AudioRecord? = null
    private var capture: Deferred<CapturedAudio>? = null
    val isRecording get() = recording

    @RequiresPermission(Manifest.permission.RECORD_AUDIO)
    fun start(scope: CoroutineScope) {
        check(!recording)
        val minimum = AudioRecord.getMinBufferSize(
            PcmWav.sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        check(minimum > 0)
        val recorder = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            PcmWav.sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            minimum * 2,
        )
        check(recorder.state == AudioRecord.STATE_INITIALIZED)
        audioRecord = recorder
        recording = true
        recorder.startRecording()
        capture = scope.async(Dispatchers.IO) {
            val output = ByteArrayOutputStream(PcmWav.maxPcmBytes)
            val buffer = ByteArray(minimum)
            try {
                while (recording && output.size() < PcmWav.maxPcmBytes) {
                    val count = recorder.read(
                        buffer,
                        0,
                        minOf(buffer.size, PcmWav.maxPcmBytes - output.size()),
                    )
                    if (count > 0) output.write(buffer, 0, count) else error("AUDIO_READ_FAILED")
                }
                PcmWav.encode(output.toByteArray())
            } finally {
                recording = false
                runCatching { recorder.stop() }
                recorder.release()
                audioRecord = null
            }
        }
    }

    suspend fun stop(discard: Boolean = false): CapturedAudio? {
        recording = false
        val result = capture?.await()
        capture = null
        return if (discard) null else result
    }
}
