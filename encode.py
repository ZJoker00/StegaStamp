import bchlib
import glob
import os
from PIL import Image,ImageOps
import numpy as np
import tensorflow as tf
import tensorflow.contrib.image
from tensorflow.python.saved_model import tag_constants
from tensorflow.python.saved_model import signature_constants

BCH_POLYNOMIAL = 137
BCH_BITS = 5

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('model', type=str)
    parser.add_argument('--image', type=str, default=None)
    parser.add_argument('--images_dir', type=str, default=None)
    parser.add_argument('--save_dir', type=str, default=None)
    parser.add_argument('--secret', type=str, default='Stega!!')
    args = parser.parse_args()

    if args.image is not None:
        files_list = [args.image]
    elif args.images_dir is not None:
        files_list = glob.glob(args.images_dir + '/*')
    else:
        print('Missing input image')
        return

    sess = tf.InteractiveSession(graph=tf.Graph())#创建并进入交互式会话，非默认；tf.Graph()创建新的计算图

    model = tf.saved_model.loader.load(sess, [tag_constants.SERVING], args.model)#将模型恢复到sess中

    input_secret_name = model.signature_def[signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY].inputs['secret'].name
    input_image_name = model.signature_def[signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY].inputs['image'].name
    input_secret = tf.get_default_graph().get_tensor_by_name(input_secret_name)#get_default_graph()当前默认的计算图，
    input_image = tf.get_default_graph().get_tensor_by_name(input_image_name)

    output_stegastamp_name = model.signature_def[signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY].outputs['stegastamp'].name
    output_residual_name = model.signature_def[signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY].outputs['residual'].name
    output_stegastamp = tf.get_default_graph().get_tensor_by_name(output_stegastamp_name)
    output_residual = tf.get_default_graph().get_tensor_by_name(output_residual_name)

    width = 400
    height = 400

    bch = bchlib.BCH(BCH_POLYNOMIAL, BCH_BITS)#BCH编码，

    if len(args.secret) > 7:
        print('Error: Can only encode 56bits (7 characters) with ECC')
        return

    data = bytearray(args.secret + ' '*(7-len(args.secret)), 'utf-8')
    ecc = bch.encode(data)
    packet = data + ecc

    packet_binary = ''.join(format(x, '08b') for x in packet)#转二进制
    secret = [int(x) for x in packet_binary]
    secret.extend([0,0,0,0])#secret序列后追加0，0，0，0

    if args.save_dir is not None:
        if not os.path.exists(args.save_dir):
            os.makedirs(args.save_dir)
        size = (width, height)
        for filename in files_list:
            image = Image.open(filename).convert("RGB")#读取图片并转RGB，不转的话读出来的图像是RGBA四通道，A为透明通道
            image = np.array(ImageOps.fit(image,size),dtype=np.float32)#ImageOps.fit()方法返回图像的大小和裁剪后的版本，裁剪为请求的宽高比和大小。
            #float32：精度浮点数，包括：1 个符号位，8 个指数位，23 个尾数位
            image /= 255.

            feed_dict = {input_secret:[secret],
                         input_image:[image]}

            hidden_img, residual = sess.run([output_stegastamp, output_residual],feed_dict=feed_dict)

            rescaled = (hidden_img[0] * 255).astype(np.uint8)#.astype转换数组数据类型
            #raw_img = (image * 255).astype(np.uint8)#uint8符号整数
            residual = residual[0]+.5

            residual = (residual * 255).astype(np.uint8)

            save_name = filename.split('/')[-1].split('.')[0]

            im = Image.fromarray(np.array(rescaled))#实现array到image的转换
            im.save(args.save_dir + '/'+save_name+'_hidden.png')

            im = Image.fromarray(np.squeeze(np.array(residual)))
            im.save(args.save_dir + '/'+save_name+'_residual.png')

if __name__ == "__main__":
    main()
