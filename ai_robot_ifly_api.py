import boto3
import json
import time
import sys
import openai
import os
openai.api_key = os.environ["OPENAI_API_KEY"]

sys.path.append("./ifly-demo")
import Ifasr_new

def generate_response(prompt):
    # Set up the OpenAI API request
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=60,
        n=1,
        stop=None,
        temperature=0.1,
    )

    # Extract the generated response
    message = completions.choices[0].text.strip()

    # Return the response
    return message

def timer(start_time, end_time, method_name):
    elapsed_time = end_time - start_time
    print(f"\n{method_name} took {elapsed_time:.2f} seconds to run.\n")

# Get the command-line arguments
args = sys.argv

# Print the arguments
print("Command-line arguments:")
print(args)
media_bucket = args[1]
media_key = args[2] 
only_transcribe = args[3]

# Set up the AWS services
polly = boto3.client('polly', region_name='us-east-1')
s3 = boto3.client('s3')
local_file_path = "question.wav"
with open(local_file_path, 'wb') as f:
    s3.download_fileobj(media_bucket, media_key, f)

ifly_start_time = time.time()
api = Ifasr_new.RequestApi(appid="148f3cf6",secret_key="25199e321b1f79e4b0df98162d9cb888",upload_file_path=local_file_path)
transcript_text = api.get_result()
ifly_end_time = time.time()
timer(ifly_start_time, ifly_end_time, "ifly job")
print('transcript_text:' + transcript_text)

if only_transcribe == '1':
    sys.exit(0)

gpt_start_time = time.time()
# Generate a response using ChatGPT
prompt = "Q: "+transcript_text+"\n"+"A:"
response = generate_response(prompt)
gpt_end_time = time.time()
timer(gpt_start_time, gpt_end_time, "GPT")

print("GPT response: "+response)

# Convert the response to speech using AWS Polly
'''
polly_start_time = time.time()
response_audio = polly.synthesize_speech(
    Text=response,
    OutputFormat='mp3',
    VoiceId='Zhiyu',
    LanguageCode='cmn-CN',
    Engine='nerual'
)

response_audio_filename = "response.mp3"

# Save the response audio to a file
with open(response_audio_filename, 'wb') as f:
    f.write(response_audio['AudioStream'].read())
polly_end_time = time.time()
timer(polly_start_time, polly_end_time, "Polly")

#send response to S3
print("send response mp3 to s3")
response_bucket_name = "lingo-audio-materials"
response_bucket_key = "answers/"+response_audio_filename
response = s3.upload_file(response_audio_filename, response_bucket_name, response_bucket_key)
print(resposne)
'''
polly_start_time = time.time()

response = polly.start_speech_synthesis_task(
    OutputS3BucketName='lingo-audio-materials', #this bucket is in us-east-1
    OutputS3KeyPrefix='answers/',
    OutputFormat='mp3',
    Text=response,
    VoiceId='Zhiyu',
    LanguageCode='cmn-CN',
    Engine='neural'
)

# Print the task ID and status
task_id = response['SynthesisTask']['TaskId']
print('Task ID:', task_id)

while True:
    task = polly.get_speech_synthesis_task(TaskId=task_id)
    task_status = task['SynthesisTask']['TaskStatus']

    if task_status == 'completed':
        break
    elif task_status  == 'failed':
        # Task failed
        print('Task failed:', task['SynthesisTask']['TaskStatusReason'])
        break
    else:
        print("Polly synthesis task is still in progress...")
        time.sleep(5)

polly_end_time = time.time()
timer(polly_start_time, polly_end_time, "Polly")
