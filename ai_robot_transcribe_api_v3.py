import boto3
import json
import time
import sys
import openai
import os
from contextlib import closing
import asyncio

# This example uses aiofile for asynchronous file reads.
# It's not a dependency of the project but can be installed
# with `pip install aiofile`.
import aiofile

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from amazon_transcribe.utils import apply_realtime_delay

"""
Here's an example of a custom event handler you can extend to
process the returned transcription results as needed. This
handler will simply print the text out to your interpreter.
"""


SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
CHANNEL_NUMS = 1


openai.api_key = os.environ["OPENAI_API_KEY"]

def polly_text_to_speech(audio_file_name, text):

    polly_response = polly.synthesize_speech(
        Text=text,
        OutputFormat='mp3',
        VoiceId='Zhiyu',
        LanguageCode='cmn-CN',
        Engine='neural',
        LexiconNames=['tigoCN']
    )
    
    # Access the audio stream from the response
    if "AudioStream" in polly_response:
        # Note: Closing the stream is important because the service throttles on the
        # number of parallel connections. Here we are using contextlib.closing to
        # ensure the close method of the stream object will be called automatically
        # at the end of the with statement's scope.
            with closing(polly_response["AudioStream"]) as stream:
               try:
                # Open a file for writing the output as a binary stream
                    with open(audio_file_name, "ab") as file:
                       file.write(stream.read())
               except IOError as error:
                  # Could not write to file, exit gracefully
                  print(error)
                  sys.exit(-1)
    
    else:
        # The response didn't contain audio data, exit gracefully
        print("Could not stream audio")
        sys.exit(-1)
    
    #file = open(response_audio_filename, 'wb')
    #file.write(polly_response['AudioStream'].read())
    #file.close()

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

#AUDIO_PATH = "./ifly-demo/rtasr_python3_demo/python/test_1.pcm"
AUDIO_PATH = media_location
CHUNK_SIZE = 1024 * 8
REGION = "us-west-2"
transcript_text = ''
transcriptions = []

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, transcript_result_stream):
            super().__init__(transcript_result_stream)
            self.transcriptions = []
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        # This handler can be implemented to handle transcriptions as needed.
        # Here's an example to get started.
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                print(alt.transcript)
                transcriptions.append(alt.transcript)


async def basic_transcribe():
    # Setup up our client with our chosen AWS region
    client = TranscribeStreamingClient(region=REGION)

    # Start transcription to generate our async stream
    stream = await client.start_stream_transcription(
        language_code="zh-CN",
        media_sample_rate_hz=SAMPLE_RATE,
        media_encoding="pcm",
    )

    async def write_chunks():
        # NOTE: For pre-recorded files longer than 5 minutes, the sent audio
        # chunks should be rate limited to match the realtime bitrate of the
        # audio stream to avoid signing issues.
        async with aiofile.AIOFile(AUDIO_PATH, "rb") as afp:
            reader = aiofile.Reader(afp, chunk_size=CHUNK_SIZE)
            await apply_realtime_delay(
                stream, reader, BYTES_PER_SAMPLE, SAMPLE_RATE, CHANNEL_NUMS
            )
        await stream.input_stream.end_stream()

    # Instantiate our handler and start processing events
    handler = MyEventHandler(stream.output_stream)
    await asyncio.gather(write_chunks(), handler.handle_events())
    # Retrieve the transcriptions from the handler
    #transcriptions = handler.transcriptions

loop = asyncio.get_event_loop()
loop.run_until_complete(basic_transcribe())
loop.close()

transcript_text = transcriptions[-1]
print("final transcribe script: "+transcript_text)
'''
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
'''
if only_transcribe == '1':
    sys.exit(0)

response_audio_filename = "response_by_polly.mp3"
if os.path.exists(response_audio_filename):
    os.remove(response_audio_filename)
    print("mp3 file deleted successfully.")
else:
    print("mp3 file does not exist.")

gpt_start_time = time.time()
tigo_saying = "你好，我是 领虎，以下是我的回答："
polly_text_to_speech(response_audio_filename, tigo_saying)
# Generate a response using ChatGPT
prompt = "Q: "+transcript_text+"\n"+"A:"
response = generate_response(prompt)
# create variables to collect the stream of events
collected_events = []
completion_text = ''
sentance_to_polly = ''
separators = ['？','。','，','！']
already_polly_processed = ''
# iterate through the stream of events
for event in response:
    collected_events.append(event)  # save the event response
    event_text = event['choices'][0]['text']  # extract the text
    if event_text in separators:
        sentance_to_polly = completion_text.replace(already_polly_processed,'') 
        #print("sentance_to_polly: "+sentance_to_polly)
        polly_text_to_speech(response_audio_filename, sentance_to_polly)
        already_polly_processed = completion_text
    completion_text += event_text  # append the text
    print(event_text, end='', flush=True)  # print the delay and text
tigo_saying = "以上是我的回答，我是 领虎，你对我的回答满意吗？"
polly_text_to_speech(response_audio_filename, tigo_saying)

# print the time delay and text received
#print(f"Full text received: {completion_text}")
gpt_end_time = time.time()
#print("GPT response: "+completion_text)
timer(gpt_start_time, gpt_end_time, "GPT and real time Polly")


#send response to S3
print("send response mp3 to s3")
response_bucket_name = "lingo-audio-materials"
response_bucket_key = "answers/"+response_audio_filename
response = s3.upload_file(response_audio_filename, response_bucket_name, response_bucket_key)
print(response)
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
print("GPT response: "+completion_text)
'''
