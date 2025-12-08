# 🎥 IMDB Sentiment Analysis with TensorFlow

This project implements a Deep Learning model to perform **Sentiment Analysis** on movie reviews. It utilizes the **Stanford NLP IMDB dataset** via the Hugging Face library and trains a Bidirectional LSTM network using TensorFlow/Keras.

The script is designed to automatically detect and utilize **TPUs (Tensor Processing Units)** for accelerated training if available, falling back to GPU or CPU otherwise.

## 📊 The Dataset

The model is trained on the Large Movie Review Dataset (IMDB).
* **Source:** [Hugging Face - stanfordnlp/imdb](https://huggingface.co/datasets/stanfordnlp/imdb)
* **Content:** 25,000 training reviews and 25,000 testing reviews.
* **Labels:** Binary classification (Positive / Negative).

## 🛠️ Tech Stack

* **Python 3.x**
* **TensorFlow & Keras:** For model building and training.
* **Hugging Face `datasets`:** For efficient data loading.
* **NumPy:** For data manipulation.

## 🧠 Model Architecture

The model uses a sequential architecture designed for Natural Language Processing (NLP):

1.  **Embedding Layer:** Converts word indices into dense vectors (Dimension: 64).
2.  **Bidirectional LSTM:** Processes sequences from both start-to-end and end-to-start to capture context (32 units).
3.  **Dense Layer:** Fully connected layer with ReLU activation.
4.  **Dropout:** Regularization layer (0.3) to prevent overfitting.
5.  **Output Layer:** Single neuron with Sigmoid activation for binary classification (0 to 1).



## 🚀 Installation

Ensure you have the necessary dependencies installed:

```bash
pip install tensorflow datasets numpy
