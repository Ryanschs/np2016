#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
from flask import Flask, request, Response, render_template, jsonify, redirect
import flask
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import bson
from cStringIO import StringIO
from PIL import Image
from imageFilter import ImageFilter
import cv2
import numpy
import json
from bson.json_util import dumps



app = Flask(__name__, static_url_path = "")
# 读取配置文件
app.config.from_object('config')
# 连接数据库，并获取数据库对象
db = MongoClient(app.config['DB_HOST'], app.config['DB_PORT']).test

def save_file(f,file_str, report_data):

	content = StringIO(file_str)

	try:	
		mime = Image.open(content).format.lower()
		print '\nmime is :', mime
		if mime not in app.config['ALLOWED_EXTENSIONS']:
			raise IOError()
	except IOError:
		flask.abort(400)
	c = dict(report_data=report_data,content=bson.binary.Binary(content.getvalue()),filename=secure_filename(f.name), mime=mime)
	db.files.save(c)
	return c['_id'], c['filename']


@app.route('/', methods=['GET', 'POST'])
def index():
	return redirect('/index.html')

@app.route('/upload', methods=['POST'])
def upload():
	if request.method == 'POST':
		if 'imagefile' not in request.files:
			flash('No file part')
			return jsonify({"error": "No file part"})
		imgfile = request.files['imagefile']
		if imgfile.filename == '':
			flash('No selected file')
			return jsonify({"error": "No selected file"})
		if imgfile:
			#pil = StringIO(imgfile)
			#pil = Image.open(pil)
			#print 'imgfile:', imgfile
			img = cv2.imdecode(numpy.fromstring(imgfile.read(), numpy.uint8), cv2.CV_LOAD_IMAGE_UNCHANGED)

			isqualified = ImageFilter(image=img).filter()
			if isqualified == None:
				error = 1
			else:
				error = 0

			'''
				使用矫正后图片执行ocr算法分割并识别图片并将识别所得的JSON数据存入mongoDB，
				这样前台点击生成报告时将直接从数据库中取出JSON数据，而不需再进行图像透视，缩短生产报告的响应时间
			'''
			with open('temp_pics/region.jpg') as f:
				'''
					使用file_str暂存文件内容，方便save_file方法使用
				'''
				file_str = f.read()
				img_region = cv2.imdecode(numpy.fromstring(file_str, numpy.uint8), cv2.CV_LOAD_IMAGE_UNCHANGED)
				if img_region is None:
					print 'img_region is None!'
				else:
					print 'img_region is NOT None!'
					report_data = ImageFilter(image = img_region).ocr(22)
					'''
						此处传入的f已是空文件，文件内容存放在file_str中，传入f的作用只为获取文件名f.name
					'''
					fid, filename = save_file(f,file_str, report_data)

			print 'fid:', fid
			#report_data = ocr.ocr(path)
			#if report_data == None:
			#	return jsonify({"error": "it is not a report"})
			#print report_data
			if 0 == error:
				templates = "<div><img id=\'filtered-report\' src=\'/file/%s\' class=\'file-preview-image\' width=\'100%%\' height=\'512\'></div>"%(fid)
				data = {
					"templates": templates,
				}
			else:
				data = {
					"error": error,
				}
			return jsonify(data)
			#return render_template("result.html", filename=filename, fileid=fid)
	#return render_template("error.html", errormessage="No POST methods")
	return jsonify({"error": "No POST methods"})

'''
	根据图像oid，在mongodb中查询，并返回Binary对象
'''
@app.route('/file/<fid>')
def find_file(fid):
	try:
		file = db.files.find_one(bson.objectid.ObjectId(fid))
		if file is None:
			raise bson.errors.InvalidId()
		return Response(file['content'], mimetype='image/' + file['mime'])
	except bson.errors.InvalidId:
		flask.abort(404)

'''
	根据报告oid，抽取透视过得图像，然后进行OCR，并返回OCR结果
'''
@app.route('/report/<fid>')
def get_report(fid):
	#print 'get_report(fid):', fid
	try:
		file = db.files.find_one(bson.objectid.ObjectId(fid))
		if file is None:
			raise bson.errors.InvalidId()
	
		'''print(type(file['content']))
		img = cv2.imdecode(numpy.fromstring(bson.json_util.loads(dumps(file['content'])), numpy.uint8), cv2.CV_LOAD_IMAGE_UNCHANGED)
		if img is None:
			print "img is None"
			return jsonify({"error": "can't ocr'"})
		report_data = ImageFilter(image=img).ocr(22)
		print report_data
		if report_data is None:
			print "report_data is None"
		'''

		'''
			直接从数据库中取出之前识别好的JSON数据，并且用bson.json_util.dumps将其从BSON转换为JSON格式的str类型
		'''
		print 'type before transform:\n', type(file['report_data'])
		
		report_data = bson.json_util.dumps(file['report_data'])

		print 'type after transform:\n', type(report_data)

		if report_data is None:
			print 'report_data is NONE! Error!!!!'
			return jsonify({"error": "can't ocr'"})

		return jsonify(report_data)
	except bson.errors.InvalidId:
		flask.abort(404)

if __name__ == '__main__':
    app.run(host=app.config['SERVER_HOST'],port=app.config['SERVER_PORT'])
