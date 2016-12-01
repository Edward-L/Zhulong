#!/usr/bin/env python2
# coding: utf-8
# file: models.py
# time: 2016/8/17 23:27

import datetime

from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.dialects.mysql import BIGINT

from Utils.CommonFunctions import generate_random_string
from Web import db
from Web import bcrypt




class ZhulongUser(db.Model):
    """
    用户表模型
    """
    __tablename__ = "zhulong_user"

    id = db.Column(BIGINT(20, unsigned=True), primary_key=True, nullable=False, autoincrement=True)
    username = db.Column(db.String(32), nullable=False, unique=True)
    email = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    last_login_time = db.Column(db.DATETIME, nullable=True, default=None)
    last_login_ip = db.Column(db.String(16), nullable=True, default=None)
    token = db.Column(db.String(64), nullable=True, default=None)
    is_active = db.Column(db.BOOLEAN, nullable=False, default=False)
    created_time = db.Column(db.DATETIME, nullable=False)

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password)

    def valid_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    def __init__(self, username=None, email=None, password=None, last_login_time=None,
                 last_login_ip=None, created_time=datetime.datetime.now()):
        self.username = username
        self.email = email
        self.set_password(password)
        self.created_time = created_time
        self.last_login_time = last_login_time
        self.last_login_ip = last_login_ip
        self.token = generate_random_string(64)
        self.is_active = False

    def __repr__(self):
        return "<Zhulong User {id}-{username}>".format(id=self.id, username=self.username)


class ZhulongUserContainers(db.Model):
    """
    记录用户创建的docker containers
    包括正在运行的以及已经停止的
    """
    __tablename__ = "zhulong_user_containers"

    id = db.Column(BIGINT(20, unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    owner_id = db.Column(BIGINT(20, unsigned=True), nullable=True, default=None)   # container拥有者ID
    image_id = db.Column(BIGINT(20, unsigned=True), nullable=True, default=None)   # image的ID
    container_name = db.Column(db.String(128), nullable=True, default=None)          # container的名称
    container_id = db.Column(db.String(64), nullable=True, default=None)            # container ID
    ssh_user = db.Column(db.String(32), nullable=True, default=None)                # SSH username
    ssh_port = db.Column(INTEGER(5, unsigned=True), nullable=True, default=None)    # SSH port
    ssh_password = db.Column(db.String(16), nullable=True, default=None)            # SSH password
    ports = db.Column(db.String(1024), nullable=True, default="{}")                 # 所有端口
    is_running = db.Column(db.BOOLEAN, nullable=True, default=False)        # container是否在运行，1-run，0-stop状态
    last_run_time = db.Column(db.DATETIME, nullable=True, default=None)     # 最后一次run时间
    last_stop_time = db.Column(db.DATETIME, nullable=True, default=None)    # 最后一次stop时间
    created_time = db.Column(db.DATETIME, nullable=True, default=None)

    def __init__(self, owner_id=None, image_id=None, container_name=None,
                 container_id=None, ssh_user=None, ssh_port=None, ssh_password=None,
                 ports=None, is_running=False, last_run_time=None, last_stop_time=None,
                 created_time=datetime.datetime.now()):
        self.owner_id = owner_id
        self.image_id = image_id
        self.container_name = container_name
        self.container_id = container_id
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.ssh_password = ssh_password
        self.ports = ports
        self.is_running = is_running
        self.last_run_time = last_run_time
        self.last_stop_time = last_stop_time
        self.created_time = created_time

    def __repr__(self):
        return "<ZhulongUserContainers {0}-{1}-{2}>".format(self.id, self.container_name, self.container_id)


class ZhulongSystemImages(db.Model):
    """
    存储基础操作系统的images
    提供给用户在此环境上进行搭建工作
    """
    __tablename__ = "zhulong_system_images"

    id = db.Column(BIGINT(20, unsigned=True), primary_key=True, autoincrement=True, nullable=False)
    op_name = db.Column(db.String(32), nullable=True, default=None)        # 操作系统名称
    server = db.Column(db.String(128), nullable=True, default="Base")        # 服务
    image_name = db.Column(db.String(32), nullable=True, default=None)     # 镜像名称 e.g. base-ubuntu:16.04
    image_id = db.Column(db.String(128), nullable=True, default=None)       # 镜像id
    expose_port = db.Column(db.String(512), nullable=True, default=None)   # 需要暴露的端口，逗号分隔: 22,80,443
    created_time = db.Column(db.DATETIME, nullable=True, default=None)

    def __init__(self, op_name=None, server="Base", image_name=None,
                 image_id=None,expose_port=None,created_time=datetime.datetime.now()):
        self.op_name = op_name
        self.server = server
        self.image_name = image_name
        self.image_id = image_id
        self.expose_port = expose_port
        self.created_time = created_time

    def __repr__(self):
        return "<ZhulongSystemImages {0}-{1}>".format(self.id, self.image_name)
