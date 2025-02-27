import datetime
from bayes_opt import BayesianOptimization
opening = datetime.datetime.now() #execution time start
import os, logging
import tensorflow as tf
import numpy as np
import data_utils as du
import sys
import warnings
import matplotlib.pyplot as plt
from sklearn.metrics import precision_score, f1_score, recall_score, accuracy_score
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from sklearn.metrics import f1_score

'''
System args: LAYER1, LAYER2, LAYER3, LR, BETA
LAYER1 = Neurons number in the first hidden layer
LAYER2 = Neurons number in the second hidden layer
LAYER3 = Neurons number in the third hidden layer
LR = learning rate
BETA = beta parameter to regularization. 0 to ignore
'''

#Train/dev/test path whitespace separated file without header. Target in the last column (data_utils)

train_path =  "/mnt/sdb/home2/mserqueira/COSMOS/dataset/cosmos_train.csv"
test_path = "/mnt/sdb/home2/mserqueira/COSMOS/dataset/cosmos_val.csv"
#train_path =  "/mnt/sdb/home2/mserqueira/COSMOS/dataset/rectangles_train.csv" #RECTANGLES
#test_path = "/mnt/sdb/home2/mserqueira/COSMOS/dataset/rectangles_val.csv"

epochs_no = 300 #Number of epochs
batch_size = 15000#32 #Batch size
patience = 15 #Number of trials to reduce epoch loss based on the min_delta
min_delta = 0.01 #min MSE reduction in each epoch
patience_cnt = 0
prior = float("inf")

trainX, trainY, predX, predY, n_classes = du.csv_to_numpy_array(train_path, test_path)
num_x = trainX.shape[1]
num_y = trainY.shape[1]

def neural_network(LAYER1, LAYER2, LAYER3, x, y):
   with tf.device('/device:GPU:0'):
    W1 = tf.Variable(tf.random_normal([num_x, LAYER1]))
    b1 = tf.Variable(tf.random_normal([LAYER1]))
    
    W2 = tf.Variable(tf.random_normal([LAYER1, LAYER2]))
    b2 = tf.Variable(tf.random_normal([LAYER2]))
    
    W3 = tf.Variable(tf.random_normal([LAYER2, LAYER3]))
    b3 = tf.Variable(tf.random_normal([LAYER3]))
    
    W_out = tf.Variable(tf.random_normal([LAYER3, n_classes]))
    b_out = tf.Variable(tf.random_normal([n_classes]))
    
    Z1 = tf.add(tf.matmul(x, W1), b1)
    A1 = tf.nn.relu(Z1)
    
    Z2 = tf.add(tf.matmul(A1, W2), b2)
    A2 = tf.nn.relu(Z2)
    
    Z3 = tf.add(tf.matmul(A2, W3), b3)
    A3 = tf.nn.relu(Z3)
    
    Z_out = tf.matmul(A3, W_out) + b_out

    return Z_out, W_out

def models_predictions(prediction, sess, x, y):
  pred_model =  tf.argmax(prediction, 1)
  pred_model = sess.run(pred_model, feed_dict={x:predX, y:predY})
  pred_true =  tf.argmax(y, 1)
  pred_true = sess.run(pred_true, feed_dict={x:predX, y:predY})

  train_model = tf.argmax(prediction, 1)
  train_model = sess.run(train_model, feed_dict={x:trainX, y:trainY})
  train_true =  tf.argmax(y, 1)
  train_true = sess.run(train_true, feed_dict={x:trainX, y:trainY})

  return pred_model, pred_true, train_model, train_true

def early_stop(epoch, epoch_loss):
  global patience_cnt
  global prior
  if epoch > 0 and prior - epoch_loss > min_delta:
    patience_cnt = 0
    flag = False
  else:
    patience_cnt += 1
    flag = False
  if patience_cnt > patience:
    flag = True
    patience_cnt = 0
    prior = float("inf")
  prior = epoch_loss
  return flag

def learning_plot(loss_train, loss_test):
  epoch_plot = range(0,len(loss_train))
  epoch_plot
  loss_test
  loss_train
  plt.plot(epoch_plot, loss_train, label="Train error")
  plt.plot(epoch_plot, loss_test, label="Test error")
  plt.legend(loc='lower left', bbox_to_anchor= (0.0, 1.01), ncol=2, 
    borderaxespad=0, frameon=False)
  #plt.legend(loc='upper right')
  plt.ylabel('Error')
  plt.xlabel('Epoch')
  plt.savefig('learning_plot.pdf')
  pass

def get_error(prediction, y, sess, labelX, labelY, x):
  correct_pred = tf.equal(tf.argmax(prediction, 1), tf.argmax(y, 1))
  accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))
  error = 1-sess.run(accuracy, feed_dict={x: labelX, y: labelY})

  return error

def build_graph(layer1, layer2, layer3, learning_rate, beta):
    with tf.device('/device:GPU:0'):  
      x = tf.placeholder(tf.float32, [None, num_x])
      y = tf.placeholder(tf.float32, [None, num_y])
      lr = tf.placeholder(tf.float32)
      prediction, weights = neural_network(int(layer1), int(layer2), int(layer3), x, y)
      
      loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=prediction, labels=y))
      regularizer = tf.nn.l2_loss(weights) #L2
      loss = tf.reduce_mean(loss + beta * regularizer)
      
      optimizer = tf.train.AdamOptimizer(lr).minimize(loss)
      #loss_train = []
      #loss_test = []
      f1_best = 0

      with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        for epoch in range(epochs_no):
          epoch_loss = 0
          i=0
          while i < len(trainX):
            start = i
            end = i+batch_size
            batch_x = np.array(trainX[start:end])
            batch_y = np.array(trainY[start:end])
            _, c = sess.run([optimizer, loss], feed_dict={x: batch_x, y: batch_y, lr: learning_rate})
            epoch_loss += c
            i+=batch_size
          
          early_flag = early_stop(epoch, epoch_loss)
          f1_epoch = get_f1(prediction, y, sess, predX, predY, x)
          if f1_epoch > f1_best:
          	f1_best = f1_epoch
          if early_flag == True:
            #print("Early stopping... ", 'Epoch', epoch+1, 'of', epochs_no, '| loss:', epoch_loss)
            break

        #if f1 > best_model: #Caso para salvar o melhor modelo...
          #saver = tf.train.Saver()
          #saver.save(sess, 'TF_model/sess/AutoML_model.ckpt')
          #np.savetxt("TF_model/test_classification.csv", pred_model.astype(int), delimiter=",")
          #print("\nBest model saved in TF_model folder")

        sess.close()

        learning_plot(loss_train, loss_test)
      return f1_best

def random_search(num_trials):
    i=0
    best_result = 0
    while i <= num_trials:
        layers1 = np.random.randint(low=5, high=15, size=1)
        layers2 = np.random.randint(low=5, high=30, size=1)
        layers3 = np.random.randint(low=5, high=45, size=1)
        lr = float(np.around(np.random.uniform(low=0.1, high=0.0001, size=1), decimals=6))
        rr = float(np.around(np.random.uniform(low=0, high=0.001, size=1), decimals=6))
        #print("Iniciando Random Serch: ", layers1[0], layers2[0], layers3[0], lr, rr, best_result)
        max_objective = build_graph(layers1[0], layers2[0], layers3[0], lr, rr)
        
        if max_objective > best_result:
            best_result = max_objective
            best_params = [layers1[0], layers2[0], layers3[0], lr, rr]
            best_trial = i
            print("Best result Updated!")
            print("F1 value: ", best_result)
            print("Trial number: ", i, "\n")
        i+=1
        tf.reset_default_graph()
    final = datetime.datetime.now()
    time = final-opening
    print("\nRandom Search final result: ", best_result)
    print("Random Search final params: ", best_params)
    print("Execution time: ", time)

def grid_search():
    i=0
    best_result = 0
    layer1 = np.array([5, 15])
    layer2 = np.array([5, 15, 30])
    layer3 = np.array([5, 15, 35, 45])
    lr = np.array([0.1, 0.01, 0.001, 0.0001, 0.00001])
    rr = np.array([0, 0.001])

    for x in range(layer1.size):
      l1 = layer1[x]
      for y in range(layer2.size):
        l2 = layer2[y]
        for z in range(layer3.size):
          l3 = layer3[z]
          for c in range(lr.size):
            lern_rate = lr[c]
            for a in range(rr.size):
              reg_rate = rr[a]
              max_objective = build_graph(l1, l2, l3, lern_rate, reg_rate)
              i+=1
              if max_objective > best_result:
                  best_result = max_objective
                  best_params = [l1, l2, l3, lern_rate, reg_rate]
                  print("Best result Updated!\n")
                  print("F1 value: ", best_result)
                  print("Trial number: ", i, "\n")
              tf.reset_default_graph()
    final = datetime.datetime.now()
    time = final-opening
    print("\nGrid Search final result: ", best_result)
    print("Grid Search final params: ", best_params)
    print("Execution time: ", time)

def bayes_opt():
  bo = BayesianOptimization(build_graph, {'layer1': (5, 15), 'layer2': (5, 30), 'layer3': (5, 45), 'learning_rate':(10e-6, 0.1), 'beta':(0, 0.001)})
  bo.maximize(init_points=40, n_iter=200, acq='ei')#acq='ucb'
  final = datetime.datetime.now()
  time = final-opening
  print("Execution time: ", time)

def get_f1(prediction, y, sess, predX, predY, x):
  pred_model =  tf.argmax(prediction, 1)
  pred_model = sess.run(pred_model, feed_dict={x:predX, y:predY})
  pred_true =  tf.argmax(y, 1)
  pred_true = sess.run(pred_true, feed_dict={x:predX, y:predY})
  f1 = f1_score(pred_true, pred_model, average='macro')

  return f1

def main():
  random_search(240)
  #grid_search()
  #bayes_opt()
  return 0

if __name__ == "__main__":
  main()
