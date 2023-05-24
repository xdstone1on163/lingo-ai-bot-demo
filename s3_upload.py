#send response to S3
import boto3
s3 = boto3.client('s3')

print("send response mp3 to s3")
response_audio_filename = "response.mp3"
response_bucket_name = "lingo-audio-material"
response_bucket_key = "answers/"+response_audio_filename
response = s3.upload_file(response_audio_filename, response_bucket_name, response_bucket_key)
print(response)
