import cv2
import requests
import tempfile
import re
from careers.models import Videos
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
# Function to extract an image from a video URL
def extract_image_from_video(video_url, output_image_path):
    try:
        # Download the video from the URL
        response = requests.get(video_url, stream=True)

        if response.status_code == 200:
            # Create a temporary file to store the video stream
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in response.iter_content(chunk_size=1024):
                    temp_file.write(chunk)

                temp_file_path = temp_file.name

            # Open the video using OpenCV
            cap = cv2.VideoCapture(temp_file_path)
            ret, frame = cap.read()

            if ret:
                # Save the frame as an image
                cv2.imwrite(output_image_path, frame)
                print("--cv2--",cv2.imwrite(output_image_path, frame))
                print(f"Image saved to {output_image_path}")
            else:
                print("Error 32: Unable to read frame from the video.")

            # Release the video capture and delete the temporary file
            cap.release()
            temp_file.close()
            return output_image_path

        else:
            print("Error 40: Unable to download the video from the URL.")

    except Exception as e:
        print(f"Error 43: {str(e)}")


def get_video_image():
    try:
        videos=Videos.objects.filter(link__isnull=False)
        print("---video-----",videos)
        for vid in videos:
            print("---vid---",vid)
            print("---vid---",vid.link)

            if (vid.link!="") and not vid.video_image:
                youtube_embed_pattern = r'https://www\.youtube\.com/embed/([a-zA-Z0-9_-]+)'
                match = re.search(youtube_embed_pattern, vid.link)

                if match:
                    # Extract the video ID from the match
                    video_id = match.group(1)
                    print(f"YouTube video ID: {video_id}")
                    y_link = f"https://i.ytimg.com/vi/{video_id}/2.jpg"
                    response = requests.get(y_link)

                    if response.status_code == 200:
                        img_temp = NamedTemporaryFile(delete=True)
                        img_temp.write(response.content)
                        img_temp.flush()

                        vid.video_image.save('vid_image.jpg', File(img_temp))
                        vid.save()
                    # Your if condition code here
                else:
                    print("No YouTube embed link found.")
                    output_image_path = "media/upload/vid_image.jpg"
                    output_image=extract_image_from_video(vid.link, output_image_path)
                    vid.video_image.save("image.jpg", File(open(output_image, 'rb')))
                    vid.save()
                    print("---video image saved---")
            else:
                continue

    except Exception as e:
        print(f"Error 92: {str(e)}")

# get_video_image()