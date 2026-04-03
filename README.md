# GPT POWERED FINANCE CHATBOT

An ethical, cost-effective, and beginner-friendly GPT-powered chatbot that educates users on personal finance, savings, budgeting, and investing.

---

## 📌 Project Overview

This project demonstrates how to build an intelligent finance assistant using **Azure OpenAI GPT-35-Turbo** and **Jupyter Notebook** with `ipywidgets` for an interactive interface. It serves as a personal chatbot for learning and discussing financial topics  all while maintaining **AI safety, fairness, and privacy**.

---

## 🎯 Features

- ✅ GPT-3.5-Turbo (Azure OpenAI) deployed via the `finance-assistant-model`.
- ✅ Ethical finance assistant with disclaimers and fairness principles.
- ✅ Built entirely using **free-tier tools and services** to keep costs minimal.
- ✅ Interactive UI using `ipywidgets` in Google Colab / Jupyter.
- ✅ Easily customizable for other domains like healthcare, HR, or education.
- ✅ Beautiful UI with markdown and emoji-enhanced responses.

---

## 🧠 System Prompt (Ethical AI Behavior)

```text
You are a helpful and ethical AI-powered finance assistant.
You educate users on personal finance, savings, budgeting, loans, and investing.

You must ensure:
- AI fairness (no biased advice or language)
- Privacy (no access to personal data)
- Transparency (state limitations clearly)
- Safety (avoid legal/investment advice)

You should:
- Use clear and inclusive language
- Recommend consulting human professionals for major decisions

---

## 🛠️ How to Recreate This Project

### 1. ✅ Prerequisites

- ✅ A free [Azure account](https://azure.microsoft.com/en-us/free/)
- ✅ Access to the [Azure OpenAI service](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- ✅ A Google account (for Google Colab)
- ✅ Basic Python knowledge

---

### 2. 🚀 Set Up Azure OpenAI & Deploy GPT-35-Turbo

1. Go to the [Azure Portal](https://portal.azure.com/)
2. Search **"Azure OpenAI"** and create a resource
3. Under your OpenAI resource:
   - Click **Deployments > + Create**
   - Select **Model**: `gpt-35-turbo`
   - **Deployment name**: `finance-assistant-model`
   - Choose pricing tier, then **Deploy**

> ✅ Keep costs low by limiting tokens (e.g., 2k TPM) and avoiding continuous streaming.

---

### 3. 📄 Clone or Copy the Notebook

1. Open Google Colab or Jupyter
2. Paste the full code from this repo into a new notebook
3. Run the cells and enter your API key and endpoint securely

---

### 4. 🧪 Ask Finance Questions

Try any of these:

- "How can I save money as a student?"
- "Explain compound interest to me like I’m five."
- "What’s a good budget plan for monthly expenses?"

---

## 📁 Project Structure

```bash
finance-assistant-chatbot/
│
├── finance_assistant_chatbot.ipynb      # Main interactive notebook
├── screenshots/                         # Place your UI and deployment screenshots here
├── README.md                            # This file
├── LICENSE                              # MIT License (optional)
└── requirements.txt                     # openai, ipywidgets, etc.
```

---

## 🔧 Customize This Bot

You can adapt this chatbot for:

- **HR Assistant**: Resume tips, job searching, interview prep
- **Healthcare Assistant**: Basic health education (with disclaimers)
- **Customer Support Bot**: FAQ answers with your company’s tone

Just modify:
- The **system prompt**
- The **deployment name**
- The **theme/UI wording**

---

## 💡 Cost-Saving Tips

- ✅ Used **free Azure credits** (trial or student)
- ✅ Limited token usage with a `max_tokens=500`
- ✅ Used **Google Colab**, no local GPU required
- ✅ No paid frontend tools — only `ipywidgets` and Markdown

---

## 🛠️ Technologies Used

| Tool               | Purpose                              |
|--------------------|--------------------------------------|
| Azure OpenAI       | GPT-3.5-Turbo Deployment             |
| Python (OpenAI SDK)| API Integration                     |
| ipywidgets         | Interactive frontend in notebook     |
| Google Colab       | Free compute & environment           |
| Markdown + CSS     | Display and style                   |

---

## 🧠 Resources for Beginners

- 🔗 [Azure OpenAI Docs](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/)
- 🔗 [Get Azure Free Credits](https://azure.microsoft.com/en-us/free/)
- 🔗 [Python OpenAI SDK](https://pypi.org/project/openai/)
- 🔗 [ipywidgets Docs](https://ipywidgets.readthedocs.io/en/stable/)
- 🔗 [Google Colab](https://colab.research.google.com/)

---

## 👨‍💻 Contributing

Feel free to fork this repo, build your own custom version, and submit a pull request!

---

## 📜 License

This project is licensed under the MIT License — see `LICENSE` for details.

---

## 💬 Connect With Me

- [GitHub](https://github.com/YOUR_USERNAME)
- [LinkedIn](https://linkedin.com/in/YOUR_PROFILE)

