from openai import OpenAI
import time

class ChatBot:

    def __init__(self, api_key, base_url, model, system_prompt, temperature=0, max_tokens=4096):
        self.history = []

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        self.system_prompt = system_prompt
        self.temperature = temperature       
        self.max_tokens = max_tokens
        self.max_context = 20

    def chat(self, prompt, prefix_output, add_to_history):
        prompts = [{"role":"system", "content": self.system_prompt}]
        
        for history in self.history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        prompts.append({"role": "user", "content": prompt})
        # prompts.append({"role": "assistant", "content": prefix_output, "prefix": True})

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        get_response = False
        while not get_response:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=prompts,
                    temperature=self.temperature,
                    # stop=["```"],
                    stream=False
                )
                res = response.choices[0].message.content
                get_response = True
            except Exception as e:
                print(e)
                time.sleep(60)

        if len(self.history) > self.max_context:
            self.history.pop()
        if add_to_history:
            self.history.append({"question":prompt,"answer":res})
        
        return res
    
    def chat_with_additional_history(self, prompt, prefix_output, add_to_history, additional_history):
        prompts = [{"role":"system", "content": self.system_prompt}]
        
        for history in additional_history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        for history in self.history:
            prompts.append({"role": "user", "content": history['question']})
            prompts.append({"role": "assistant", "content": history['answer']})
        
        prompts.append({"role": "user", "content": prompt})
        # prompts.append({"role": "assistant", "content": prefix_output, "prefix": True})

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        response = client.chat.completions.create(
            model=self.model,
            messages=prompts,
            temperature=self.temperature,
            # stop=["```"],
            stream=False
        )
        
        try:
            rate_limit = response.message
            if 'limit' in rate_limit:
                time.sleep(60)
                response = client.chat.completions.create(
                    model=self.model,
                    messages=prompts,
                    temperature=self.temperature,
                    # stop=["```"],
                    stream=False
                )
        except Exception as e:
            pass
            
        res = response.choices[0].message.content
        
        if len(self.history) > self.max_context:
            self.history.pop()
        if add_to_history:
            self.history.append({"question":prompt,"answer":res})
        
        return res

    
    def clear_history(self):
        self.history = []
        
        
    def add_history(self, question, answer):
        if len(self.history) > self.max_context:
            self.history.pop()
        self.history.append({"question": question, "answer": answer})
        
    def show_history(self):
        print('=' * 20)
        print('System Prompt:')
        print(self.system_prompt)
        for history in self.history:
            print("Question:")
            print(history["question"])
            print("Answer:")
            print(history["answer"])
            print("-" * 20)
        print('=' * 20)

    def get_history(self, additional_history=[]):
        # concat history to string
        history_str = ''
        for history in additional_history:
            history_str += f"Question: {history['question']}\n"
            history_str += f"Answer: {history['answer']}\n"
        
        for history in self.history:
            history_str += f"Question: {history['question']}\n"
            history_str += f"Answer: {history['answer']}\n"
        return history_str

if __name__ == "__main__":
    chatbot = ChatBot('')

    prompt = 'hi'
    chatbot.chat(prompt, '',True)
    
    # display(chatbot.history)
    for history in chatbot.history:
        print("Question:")
        print(history["question"])
        print("Answer:")
        print(history["answer"])
    print("----")
