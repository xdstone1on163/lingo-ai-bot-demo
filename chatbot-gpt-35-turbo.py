import openai
import time
import os

openai.api_key = os.environ["OPENAI_API_KEY"]


# Note: you need to be using OpenAI Python v0.27.0 for the code below to work

def ask_gpt3_turbo(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a teacher, will teach students from 3 to 10 years old Chinese, you will answer questions with Chinese. You will only answer questions related to Chinese learning."},
            {"role": "user", "content": "成语：狐假虎威 是什么意思？"},
            {"role": "assistant", "content": "成语 狐假虎威 的意思是一个人没有真正的本领，却想躲在另一个人的后面借助他人的力量。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5, 
        max_tokens=512, 
        presence_penalty=0, 
        frequency_penalty=2, 
        n=1,
        stream=True
    )      
    #message = response["choices"][0]["message"]["content"]
    #return message
    return response
    
print("hello, I am a chatbot, please shoot me your questions:")

questions = []
answers = []

def generate_prompt(prompt, questions, answers):
    num = len(answers)
    for i in range(num):
        prompt += "\n Q : " + questions[i]
        prompt += "\n A : " + answers[i]
    prompt += "\n Q : " + questions[num] + "\n A : "        
    return prompt

while True:
    user_input = input("> ")
    questions.append(user_input)
    if user_input.lower() in ["bye", "goodbye", "exit"]:
        print("Goodbye!")
        break
    
    prompt = generate_prompt("", questions, answers)

    answer = ask_gpt3_turbo(prompt)
    #print(answer)

    # create variables to collect the stream of chunks
    collected_chunks = []
    collected_messages = []
    # iterate through the stream of events
    for chunk in answer:
        collected_chunks.append(chunk)  # save the event response
        chunk_message = chunk['choices'][0]['delta']  # extract the message
        collected_messages.append(chunk_message)  # save the message
        if "content" in chunk_message:
            print(chunk_message['content'], end='', flush=True)  # print the delay and text
    
    full_reply_content = ''.join([m.get('content', '') for m in collected_messages])
    #print(f"Full conversation received: {full_reply_content}")
    print("\n")

    answers.append(full_reply_content)
