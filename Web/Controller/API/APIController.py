#!/usr/bin/env python2
# coding: utf-8
# file: APIController.py
# time: 2016/9/6 21:11
import datetime
import json

from flask import jsonify, request, g

from Utils.LoggerHelp import logger
from Web import web, db, docker_client
from Web.models import ZhulongSystemImages
from Web.models import ZhulongUserContainers
from Utils.LoginRequire import login_required
from Utils.CommonFunctions import generate_random_string





@web.route("/api/v1/get_info", methods=['GET'])
@login_required
def api_get_info():

    # 获取所有的系统镜像名称
    results = ZhulongSystemImages.query.group_by(ZhulongSystemImages.op_name).all()
    op_images_info = dict()

    try:
        for res in results:
            op_images_info[res.op_name] = list()

            # 获取对应系统镜像的服务和ID信息
            servers = ZhulongSystemImages.query.filter(
                ZhulongSystemImages.op_name == res.op_name
            ).group_by(ZhulongSystemImages.server).all()

            # 整理数据
            op_images_info[res.op_name] = [dict(value=ser.id, server=ser.server) for ser in servers]
    except Exception as e:
        return jsonify(code=1004, message=e.message)

    return jsonify(info=op_images_info, code=1001, message="Successful")

@web.route("/api/v1/get_containers", methods=['GET'])
@login_required
def api_get_containers():
    # 获取该用户所有的contariners
    results = ZhulongUserContainers.query.filter(ZhulongUserContainers.owner_id == g.current_user.id).all()
    contariners_info = dict()

    try:
        for res in results:
            # 整理数据
            cid = "container" + str(res.id)
            last_run_time = str(res.last_run_time) 
            last_stop_time = str(res.last_stop_time)
            if res.is_running:
                opstate = "stop"
                state = "running"
                butCol = "btn-primary"
            else:
                opstate = "start"
                state = "stoped"
                butCol = "btn-success"
            postinfo = res.ports.replace(" ","").replace("{","").replace("}","").replace("\":","->").replace("\"","").replace(",","\n")

            contariners_info[cid] = dict(butCol = butCol, conid=res.container_id,opstate=opstate, container_name=res.container_name, ssh_user=res.ssh_user, ssh_port=res.ssh_port, ssh_password=res.ssh_password,ports=postinfo, is_running=state, last_run_time=last_run_time, last_stop_time=last_stop_time)
    except Exception as e:
        return jsonify(code=1004, message=e.message)

    return jsonify(info=contariners_info, code=1001, message="Successful")


@web.route("/api/v1/create_docker", methods=["POST"])
@login_required
def api_create_docker():
    print request.json
    exposed_port = request.json.get("port", "")
    server_id = request.json.get("server_id", "")
    container_name = request.json.get("container_name", "")

    if server_id == "":
        return jsonify(code=1004, message="服务版本选择有误")

    # 检查server_id
    system_image = ZhulongSystemImages.query.filter(ZhulongSystemImages.id == server_id).first()
    if not system_image:
        return jsonify(code=1004, message="系统版本选择有误")
    logger.debug(system_image)

    # 检查container name
    if container_name == "":
        return jsonify(code=1004, message="Container名称不能为空")
    container_name = g.current_user.username + "_" + container_name
    tmp = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_name == container_name).first()
    if tmp:
        return jsonify(code=1004, message="Container名称重复")

    # 整理port
    try:
        ports = [int(p.strip()) for p in exposed_port.split(",")]
        for port in system_image.expose_port.split(","):
            logger.debug(ports)
            if port not in ports:
                ports.append(int(port))
    except ValueError:
        return jsonify(code=1004, message="端口填写有误")
    logger.debug(ports)

    # 默认开启22端口
    if 22 not in ports:
        ports.append(22)

    # 调用docker API跑起container
    image_name = system_image.image_name
    container = docker_client.create_container(
        image=image_name,
        ports=ports,
        name=container_name,
        host_config=docker_client.create_host_config(
            publish_all_ports=True
        )
    )
    logger.debug(container)
    docker_client.start(container.get("Id"))

    # 生成随机密码
    new_password = generate_random_string(12)
    # 改密码
    exec_id = docker_client.exec_create(
        container.get("Id"),
        'bash -c "echo root:{0} | chpasswd"'.format(new_password)
    )
    logger.debug(exec_id)
    docker_client.exec_start(exec_id.get("Id"))
    logger.info("exec done.")

    # 获取端口信息，改成json格式存入数据库
    # todo 多线程
    published_ports = dict()
    ssh_port = None
    for port in ports:
        response = docker_client.port(container.get("Id"), port)[0]
        published_ports[port] = response.get("HostIp") + ":" + response.get("HostPort")
        if port == 22:
            ssh_port = response.get("HostPort")
        print published_ports[port]
    published_ports = json.dumps(published_ports)

    # 插入到数据库中
    user_container = ZhulongUserContainers(
        owner_id=g.current_user.id, image_id=system_image.id, 
        container_name=container_name, container_id=container.get("Id"), ssh_user="root",
        ssh_port=ssh_port, ssh_password=new_password, 
        ports=published_ports, is_running=True,
        last_run_time=datetime.datetime.now(), last_stop_time=None
    )
    try:
        db.session.add(user_container)
        db.session.commit()
    except Exception as e:
        logger.error(e)
        return jsonify(code=1004, message="数据库执行失败，请稍后再试。")
    return jsonify(code=1001, message="container生成成功！")


@web.route("/api/v1/start_container", methods=["POST"])
@login_required
def api_start_container():
    print request.json
    conid = request.json.get("conid", "")

    # 检查container_id
    choose_container = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_id == conid).first()
    if not choose_container:
        return jsonify(code=1004, message="container选择有误")
    logger.debug(choose_container)

    # 调用docker API start container
    container = docker_client.start(container=conid)
    
    logger.debug(container)
    # 获取端口信息，改成json格式存入数据库
    # todo 多线程
    tmp = choose_container.ports
    tmp = json.loads(tmp)
    ports = []
    for i in tmp:
        ports.append(i)
    published_ports = dict()
    ssh_port = None
    for port in ports:
        response = docker_client.port(conid, port)[0]
        published_ports[port] = response.get("HostIp") + ":" + response.get("HostPort")
        if port == "22":
            ssh_port = int(response.get("HostPort"))
        print published_ports[port]
    published_ports = json.dumps(published_ports)

    choose_container.is_running = True
    choose_container.last_run_time = datetime.datetime.now()
    choose_container.ssh_port = ssh_port
    choose_container.ports = published_ports
    # 插入到数据库中
    try:
        db.session.add(choose_container)
        db.session.commit()
    except Exception as e:
        logger.error(e)
        return jsonify(code=1004, message="数据库执行失败，请稍后再试。")
    return jsonify(code=1001, message="start container 成功！")

@web.route("/api/v1/stop_container", methods=["POST"])
@login_required
def api_stop_container():
    print request.json
    conid = request.json.get("conid", "")

    # 检查container_id
    container = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_id == conid).first()
    if not container:
        return jsonify(code=1004, message="container选择有误")
    logger.debug(container)

    # 调用docker API stop container
    container = docker_client.stop(container=conid)
    
    logger.debug(container)

    choose_container = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_id == conid).first()
    choose_container.is_running = False
    choose_container.last_stop_time = datetime.datetime.now()
    # 插入到数据库中
    try:
        db.session.add(choose_container)
        db.session.commit()
    except Exception as e:
        logger.error(e)
        return jsonify(code=1004, message="数据库执行失败，请稍后再试。")
    return jsonify(code=1001, message="start container 成功！")


@web.route("/api/v1/del_container", methods=["POST"])
@login_required
def api_del_container():
    print request.json
    conid = request.json.get("conid", "")

    # 检查container_id
    container = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_id == conid).first()
    if container.is_running:
        return jsonify(code=1004, message="container is runnning~ stop it first !!")
    logger.debug(container)

    # 调用docker API stop container
    container = docker_client.remove_container(container=conid)
    
    logger.debug(container)

    choose_container = ZhulongUserContainers.query.filter(ZhulongUserContainers.container_id == conid).first()

    # 插入到数据库中
    try:
        db.session.delete(choose_container)
        db.session.commit()
    except Exception as e:
        logger.error(e)
        return jsonify(code=1004, message="数据库执行失败，请稍后再试。")
    return jsonify(code=1001, message="delete container 成功！")




