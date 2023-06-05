#send response to S3
import boto3

def generate_presigned_url(bucket_name, object_key, expiration_time=3600):
    s3_client = boto3.client('s3')
    
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': object_key
            },
            ExpiresIn=expiration_time
        )
        
        return response
    
    except NoCredentialsError:
        print("AWS credentials not found.")
        return None

s3 = boto3.client('s3')

bucket_name = 'lingo-audio-material'
response_audio_filename = "response_by_polly.mp3"
bucket_key = "answers/"+response_audio_filename

print("send response mp3 to s3")
response = s3.upload_file(response_audio_filename, bucket_name, bucket_key)
print(response)


presigned_url = generate_presigned_url(bucket_name, bucket_key)
if presigned_url is not None:
    print(f"Pre-signed URL: {presigned_url}")
else:
    print("Failed to generate pre-signed URL.")
