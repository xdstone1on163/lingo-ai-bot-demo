import boto3
import json
import time
import sys
import openai
import os
openai.api_key = os.environ["OPENAI_API_KEY"]

sys.path.append('./ifly-demo')
import Ifasr_new

def generate_response(prompt):
    # Set up the OpenAI API request
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.1,
        top_p=1,
        stream=True
    )

    # Extract the generated response when it is not streaming response
    #message = completions.choices[0].text.strip()
    # Return the response
    #return message
    return completions

def timer(start_time, end_time, method_name):
    elapsed_time = end_time - start_time
    print(f"\n{method_name} took {elapsed_time:.2f} seconds to run.\n")

# Get the command-line arguments
args = sys.argv

# Print the arguments
print("Command-line arguments:")
print(args)
# take 2 args, arg1: jobname, arg2:media file s3 location

job_name = args[1]
media_location = args[2] 
only_transcribe = args[3]

# Set up the AWS services
transcribe = boto3.client('transcribe')
polly = boto3.client('polly', region_name='us-east-1')
s3 = boto3.client('s3')

response = transcribe.list_transcription_jobs()

# Iterate through the jobs and print their names
for job in response['TranscriptionJobSummaries']:
    print(job['TranscriptionJobName'])
    if job['TranscriptionJobName'] == job_name:
        response = transcribe.delete_transcription_job(TranscriptionJobName=job_name)
        print("delete transcribe job response:"+str(response))

# Set up the job parameters
text_output_bucket = 'lingo-text-material' #this bucket is in us-west-1
text_output_key = 'transcriptions/'+job_name+'.json'
language_code = 'zh-CN'

transcribe_start_time = time.time()
# Create the transcription job
response = transcribe.start_transcription_job(
    TranscriptionJobName=job_name,
    Media={'MediaFileUri': media_location},
    MediaFormat='wav',
    LanguageCode=language_code,
    OutputBucketName=text_output_bucket,
    OutputKey=text_output_key
)

print("start transcribe job response:"+str(response))

# Wait for the transcription job to complete
while True:
    status = transcribe.get_transcription_job(TranscriptionJobName=job_name)['TranscriptionJob']['TranscriptionJobStatus']
    if status in ['COMPLETED', 'FAILED']:
        break
    print("Transcription job still in progress...")
    time.sleep(5)

# Get the transcript
#transcript = transcribe.get_transcription_job(TranscriptionJobName=job_name)
transcript_uri = transcribe.get_transcription_job(TranscriptionJobName=job_name)['TranscriptionJob']['Transcript']['TranscriptFileUri']
print("transcript uri: " + str(transcript_uri))
transcribe_end_time = time.time()
timer(transcribe_start_time, transcribe_end_time, "transcribe")

transcript_file_content = s3.get_object(Bucket=text_output_bucket, Key=text_output_key)['Body'].read().decode('utf-8')
print(transcript_file_content)

json_data = json.loads(transcript_file_content)

# Extract the transcript value
transcript_text = json_data['results']['transcripts'][0]['transcript']
print('transcript_text:' + transcript_text)

if only_transcribe == '1':
    sys.exit(0)

gpt_start_time = time.time()
# Generate a response using ChatGPT
prompt = "Q: "+transcript_text+"\n"+"A:"
response = generate_response(prompt)
# create variables to collect the stream of events
collected_events = []
completion_text = ''
# iterate through the stream of events
for event in response:
    collected_events.append(event)  # save the event response
    event_text = event['choices'][0]['text']  # extract the text
    completion_text += event_text  # append the text
    print(event_text, end='', flush=True)  # print the delay and text
# print the time delay and text received
#print(f"Full text received: {completion_text}")
gpt_end_time = time.time()
timer(gpt_start_time, gpt_end_time, "GPT")

print("GPT response: "+completion_text)

# Convert the response to speech using AWS Polly
'''
polly_start_time = time.time()
response_audio = polly.synthesize_speech(
    Text=completion_text,
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
    Text=completion_text,
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
