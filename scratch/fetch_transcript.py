from youtube_transcript_api import YouTubeTranscriptApi
import json

video_id = "4_33Wsc9fcg"
try:
    transcripts = YouTubeTranscriptApi.get_transcript(video_id, languages=['hi', 'en', 'en-IN'])
    text = "\n".join([t['text'] for t in transcripts])
    with open("transcript.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Success")
except Exception as e:
    print("Direct fetch failed, trying full list.")
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for t in transcript_list:
            print("Available transcript:", t.language, t.language_code, t.is_generated)
            text_data = t.fetch()
            text = "\n".join([item['text'] for item in text_data])
            with open("transcript.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("Successfully saved:", t.language)
            break
    except Exception as e2:
        print("Failed to get any transcript:", e2)
