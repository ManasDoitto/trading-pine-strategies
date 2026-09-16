import sys
from youtube_transcript_api import YouTubeTranscriptApi

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t['text'] for t in transcript])
        print(text)
    except Exception as e:
        print(f"Error getting transcript for {video_id}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_transcript(sys.argv[1])
    else:
        print("Please provide a video ID")
