import os
import logging
import torch
import argparse
import json
# 日志格式
LOG_FORMAT = "%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format=LOG_FORMAT)

import argparse
import json

parser = argparse.ArgumentParser()
#------multi worker-----------------
parser.add_argument('--model-path-address',
                    default="THUDM/chatglm2-6b@localhost@20002",
                    nargs="+",
                    type=str,
                    help="model path, host, and port, formatted as model-path@host@path")
#---------------controller-------------------------

parser.add_argument("--controller-host", type=str, default="localhost")
parser.add_argument("--controller-port", type=int, default=21001)
parser.add_argument(
    "--dispatch-method",
    type=str,
    choices=["lottery", "shortest_queue"],
    default="shortest_queue",
)
controller_args = ["controller-host","controller-port","dispatch-method"]

#----------------------worker------------------------------------------

parser.add_argument("--worker-host", type=str, default="localhost")
parser.add_argument("--worker-port", type=int, default=21002)
# parser.add_argument("--worker-address", type=str, default="http://localhost:21002")
# parser.add_argument(
#     "--controller-address", type=str, default="http://localhost:21001"
# )
parser.add_argument(
    "--model-path",
    type=str,
    default="lmsys/vicuna-7b-v1.3",
    help="The path to the weights. This can be a local folder or a Hugging Face repo ID.",
)
parser.add_argument(
    "--revision",
    type=str,
    default="main",
    help="Hugging Face Hub model revision identifier",
)
parser.add_argument(
    "--device",
    type=str,
    choices=["cpu", "cuda", "mps", "xpu"],
    default="cuda",
    help="The device type",
)
parser.add_argument(
    "--gpus",
    type=str,
    default="0",
    help="A single GPU like 1 or multiple GPUs like 0,2",
)
parser.add_argument("--num-gpus", type=int, default=1)
parser.add_argument(
    "--max-gpu-memory",
    type=str,
    help="The maximum memory per gpu. Use a string like '13Gib'",
)
parser.add_argument(
    "--load-8bit", action="store_true", help="Use 8-bit quantization"
)
parser.add_argument(
    "--cpu-offloading",
    action="store_true",
    help="Only when using 8-bit quantization: Offload excess weights to the CPU that don't fit on the GPU",
)
parser.add_argument(
    "--gptq-ckpt",
    type=str,
    default=None,
    help="Load quantized model. The path to the local GPTQ checkpoint.",
)
parser.add_argument(
    "--gptq-wbits",
    type=int,
    default=16,
    choices=[2, 3, 4, 8, 16],
    help="#bits to use for quantization",
)
parser.add_argument(
    "--gptq-groupsize",
    type=int,
    default=-1,
    help="Groupsize to use for quantization; default uses full row.",
)
parser.add_argument(
    "--gptq-act-order",
    action="store_true",
    help="Whether to apply the activation order GPTQ heuristic",
)
parser.add_argument(
    "--model-names",
    type=lambda s: s.split(","),
    help="Optional display comma separated names",
)
parser.add_argument(
    "--limit-worker-concurrency",
    type=int,
    default=5,
    help="Limit the model concurrency to prevent OOM.",
)
parser.add_argument("--stream-interval", type=int, default=2)
parser.add_argument("--no-register", action="store_true")

worker_args = [
                "worker-host","work-port",
                "model-path","revision","device","gpus","num-gpus",
               "max-gpu-memory","load-8bit","cpu-offloading",
               "gptq-ckpt","gptq-wbits","gptq-groupsize",
               "gptq-act-order","model-names","limit-worker-concurrency",
               "stream-interval","no-register",
               "controller-address"
               ]
#-----------------openai server---------------------------

parser.add_argument("--server-host", type=str, default="localhost", help="host name")
parser.add_argument("--server-port", type=int, default=8001, help="port number")
parser.add_argument(
    "--allow-credentials", action="store_true", help="allow credentials"
)
# parser.add_argument(
#     "--allowed-origins", type=json.loads, default=["*"], help="allowed origins"
# )
# parser.add_argument(
#     "--allowed-methods", type=json.loads, default=["*"], help="allowed methods"
# )
# parser.add_argument(
#     "--allowed-headers", type=json.loads, default=["*"], help="allowed headers"
# )
parser.add_argument(
    "--api-keys",
    type=lambda s: s.split(","),
    help="Optional list of comma separated API keys",
)
server_args = ["server-host","server-port","allow-credentials","api-keys",
               "controller-address"
               ]
#-------------------似乎也可以在这里把所有可配置的项目做成命令行-----------------------




# 在以下字典中修改属性值，以指定本地embedding模型存储位置
# 如将 "text2vec": "GanymedeNil/text2vec-large-chinese" 修改为 "text2vec": "User/Downloads/text2vec-large-chinese"
# 此处请写绝对路径
embedding_model_dict = {
    "ernie-tiny": "nghuyong/ernie-3.0-nano-zh",
    "ernie-base": "nghuyong/ernie-3.0-base-zh",
    "text2vec-base": "shibing624/text2vec-base-chinese",
    "text2vec": "GanymedeNil/text2vec-large-chinese",
    "text2vec-paraphrase": "shibing624/text2vec-base-chinese-paraphrase",
    "text2vec-sentence": "shibing624/text2vec-base-chinese-sentence",
    "text2vec-multilingual": "shibing624/text2vec-base-multilingual",
    "m3e-small": "moka-ai/m3e-small",
    "m3e-base": "moka-ai/m3e-base",
    "m3e-large": "moka-ai/m3e-large",
}

# 选用的 Embedding 名称
EMBEDDING_MODEL = "text2vec"

# Embedding 模型运行设备
EMBEDDING_DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


llm_model_dict = {
    "chatglm-6b": {
        "local_model_path": "THUDM/chatglm-6b",
        "api_base_url": "http://localhost:8888/v1",  # "name"修改为fastchat服务中的"api_base_url"
        "api_key": "EMPTY"
    },

    "chatglm-6b-int4": {
        "local_model_path": "THUDM/chatglm-6b-int4",
        "api_base_url": "http://localhost:8001/v1",  # "name"修改为fastchat服务中的"api_base_url"
        "api_key": "EMPTY"
    },

    "chatglm2-6b": {
        "local_model_path": "THUDM/chatglm2-6b",
        "api_base_url": "http://localhost:8888/v1",  # "name"修改为fastchat服务中的"api_base_url"
        "api_key": "EMPTY"
    },

    "vicuna-13b-hf": {
        "local_model_path": "",
        "api_base_url": "http://localhost:8000/v1",  # "name"修改为fastchat服务中的"api_base_url"
        "api_key": "EMPTY"
    },

    # 调用chatgpt时如果报出： urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='api.openai.com', port=443):
    #  Max retries exceeded with url: /v1/chat/completions
    # 则需要将urllib3版本修改为1.25.11
    # 如果依然报urllib3.exceptions.MaxRetryError: HTTPSConnectionPool，则将https改为http
    # 参考https://zhuanlan.zhihu.com/p/350015032

    # 如果报出：raise NewConnectionError(
    # urllib3.exceptions.NewConnectionError: <urllib3.connection.HTTPSConnection object at 0x000001FE4BDB85E0>:
    # Failed to establish a new connection: [WinError 10060]
    # 则是因为内地和香港的IP都被OPENAI封了，需要切换为日本、新加坡等地
    "openai-chatgpt-3.5": {
        "local_model_path": "gpt-3.5-turbo",
        "api_base_url": "https://api.openapi.com/v1",
        "api_key": os.environ.get("OPENAI_API_KEY")
    },
}

# LLM 名称
LLM_MODEL = "chatglm2-6b"

# LLM 运行设备
LLM_DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

# 日志存储路径
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
if not os.path.exists(LOG_PATH):
    os.mkdir(LOG_PATH)

# 知识库默认存储路径
KB_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base")

# nltk 模型存储路径
NLTK_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nltk_data")

# 基于本地知识问答的提示词模版
PROMPT_TEMPLATE = """【指令】根据已知信息，简洁和专业的来回答问题。如果无法从中得到答案，请说 “根据已知信息无法回答该问题”，不允许在答案中添加编造成分，答案请使用中文。 

【已知信息】{context} 

【问题】{question}"""

# API 是否开启跨域，默认为False，如果需要开启，请设置为True
# is open cross domain
OPEN_CROSS_DOMAIN = False