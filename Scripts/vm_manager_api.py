from fastapi import FastAPI, HTTPException
import subprocess
import os
import ssl
import time

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

app = FastAPI()

# =========================
# CONFIG
# =========================

ESXI_USER = "root"
ESXI_PASSWORD = "toto32**"

OVA_PATH = "/home/limam/dev/Hackathon/AlpineV_Custom.ova"
DATACENTER_NAME = "ha-datacenter"
DATASTORE_NAME = "vsanDatastore"
RESOURCE_POOL = "Resources"

PROTECTED_HOST = "10.144.208.124"   # toujours running, jamais touché
STANDBY_HOST = "10.144.208.122"     # toujours présente, running ou suspended
EXTRA_HOST = "10.144.208.123"       # absente / suspended / running

VM_NAME = "AlpineV"

DEPLOY_OVA_SCRIPT = "samples/deploy_ova.py"
DESTROY_VM_SCRIPT = "samples/destroy_vm.py"


# =========================
# CONNECTION
# =========================

def connect_esxi(host: str):
    context = ssl._create_unverified_context()
    si = SmartConnect(
        host=host,
        user=ESXI_USER,
        pwd=ESXI_PASSWORD,
        sslContext=context
    )
    return si


def wait_for_task(task, action_name="task", timeout=300):
    start = time.time()

    while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
        if time.time() - start > timeout:
            raise TimeoutError(f"{action_name} timed out")
        time.sleep(1)

    if task.info.state == vim.TaskInfo.State.success:
        return task.info.result

    error_msg = str(task.info.error) if task.info.error else "Unknown error"
    raise Exception(f"{action_name} failed: {error_msg}")


# =========================
# READ HELPERS
# =========================

def list_host_vms(host: str):
    si = None
    try:
        si = connect_esxi(host)
        content = si.RetrieveContent()

        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )

        result = []
        try:
            for vm in container.view:
                result.append({
                    "name": vm.summary.config.name,
                    "state": str(vm.summary.runtime.powerState),
                    "ip_address": vm.guest.ipAddress,
                    "tools_status": str(vm.guest.toolsRunningStatus)
                })
        finally:
            container.Destroy()

        return result
    finally:
        if si:
            Disconnect(si)


def get_vm_info_on_host(host: str, vm_name: str):
    si = None
    try:
        si = connect_esxi(host)
        content = si.RetrieveContent()

        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )

        try:
            for vm in container.view:
                if vm.summary.config.name == vm_name:
                    return {
                        "name": vm.summary.config.name,
                        "state": str(vm.summary.runtime.powerState),
                        "ip_address": vm.guest.ipAddress,
                        "tools_status": str(vm.guest.toolsRunningStatus)
                    }
        finally:
            container.Destroy()

        return None
    finally:
        if si:
            Disconnect(si)


def get_vm_state(host: str):
    info = get_vm_info_on_host(host, VM_NAME)
    return None if info is None else info["state"]


def has_vm(host: str) -> bool:
    return get_vm_info_on_host(host, VM_NAME) is not None


def wait_for_vm_ip(host: str, vm_name: str, timeout=120):
    start = time.time()

    while time.time() - start < timeout:
        info = get_vm_info_on_host(host, vm_name)
        if info and info["state"] == "poweredOn" and info["ip_address"]:
            return info["ip_address"]
        time.sleep(2)

    return None


# =========================
# SCRIPT HELPERS
# =========================

def run_python_script(cmd):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        raise Exception(
            f"Command failed\nCMD: {' '.join(cmd)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    return result.stdout


def deploy_vm_on_host(target_host: str):
    cmd = [
        "python3",
        DEPLOY_OVA_SCRIPT,
        "--host", target_host,
        "--user", ESXI_USER,
        "--password", ESXI_PASSWORD,
        "--datacenter-name", DATACENTER_NAME,
        "--datastore-name", DATASTORE_NAME,
        "--resource-pool", RESOURCE_POOL,
        "--ova-path", OVA_PATH,
        "-nossl"
    ]

    stdout = run_python_script(cmd)

    return {
        "message": f"VM deployed on {target_host}",
        "vm_name": VM_NAME,
        "stdout": stdout,
        "vm_info": get_vm_info_on_host(target_host, VM_NAME)
    }


def destroy_vm_on_host(target_host: str):
    if target_host in [PROTECTED_HOST, STANDBY_HOST]:
        raise Exception(f"Refused: host {target_host} cannot be destroyed in this strategy")

    cmd = [
        "python3",
        DESTROY_VM_SCRIPT,
        "--host", target_host,
        "--user", ESXI_USER,
        "--password", ESXI_PASSWORD,
        "--vm-name", VM_NAME,
        "-nossl"
    ]

    stdout = run_python_script(cmd)

    return {
        "message": f"VM destroyed on {target_host}",
        "vm_name": VM_NAME,
        "stdout": stdout
    }


# =========================
# DIRECT PYVMOMI ACTIONS
# =========================

def suspend_vm_on_host(target_host: str):
    if target_host == PROTECTED_HOST:
        raise Exception(f"Refused: {PROTECTED_HOST} must always stay running")

    si = None
    try:
        si = connect_esxi(target_host)
        content = si.RetrieveContent()

        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )

        vm_obj = None
        try:
            for vm in container.view:
                if vm.summary.config.name == VM_NAME:
                    vm_obj = vm
                    break
        finally:
            container.Destroy()

        if vm_obj is None:
            raise Exception(f"{VM_NAME} not found on {target_host}")

        state = vm_obj.runtime.powerState
        if state == vim.VirtualMachinePowerState.suspended:
            return {
                "message": f"{VM_NAME} already suspended on {target_host}",
                "vm_info": get_vm_info_on_host(target_host, VM_NAME)
            }

        if state != vim.VirtualMachinePowerState.poweredOn:
            raise Exception(f"{VM_NAME} on {target_host} is not running, current state: {state}")

        task = vm_obj.SuspendVM_Task()
        wait_for_task(task, f"Suspend {VM_NAME}")

        return {
            "message": f"{VM_NAME} suspended on {target_host}",
            "vm_info": get_vm_info_on_host(target_host, VM_NAME)
        }
    finally:
        if si:
            Disconnect(si)


def resume_vm_on_host(target_host: str):
    si = None
    try:
        si = connect_esxi(target_host)
        content = si.RetrieveContent()

        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )

        vm_obj = None
        try:
            for vm in container.view:
                if vm.summary.config.name == VM_NAME:
                    vm_obj = vm
                    break
        finally:
            container.Destroy()

        if vm_obj is None:
            raise Exception(f"{VM_NAME} not found on {target_host}")

        state = vm_obj.runtime.powerState
        if state == vim.VirtualMachinePowerState.poweredOn:
            return {
                "message": f"{VM_NAME} already running on {target_host}",
                "vm_info": get_vm_info_on_host(target_host, VM_NAME)
            }

        task = vm_obj.PowerOnVM_Task()
        wait_for_task(task, f"Resume {VM_NAME}")

        ip = wait_for_vm_ip(target_host, VM_NAME, timeout=60)

        info = get_vm_info_on_host(target_host, VM_NAME)
        if info:
            info["ip_address"] = ip or info["ip_address"]

        return {
            "message": f"{VM_NAME} resumed on {target_host}",
            "vm_info": info
        }
    finally:
        if si:
            Disconnect(si)



def action_up():
    """
    Cas 1
      124 running
      122 suspended
      123 absent
      => resume 122
      => create 123
      => run then suspend 123

    Cas 2
      124 running
      122 running
      123 suspended
      => resume 123

    Sinon
      no action
    """
    state_124 = get_vm_state(PROTECTED_HOST)
    state_122 = get_vm_state(STANDBY_HOST)
    state_123 = get_vm_state(EXTRA_HOST)

    if state_124 != "poweredOn":
        raise Exception(f"{PROTECTED_HOST} must always be running, current state: {state_124}")

    # Cas 1
    if state_122 == "suspended" and state_123 is None:
        result = {}

        result["step1_resume_122"] = resume_vm_on_host(STANDBY_HOST)

        result["step2_create_123"] = deploy_vm_on_host(EXTRA_HOST)

        # après le déploiement, on la démarre
        result["step3_run_123"] = resume_vm_on_host(EXTRA_HOST)

        # puis on la suspend pour garder toujours une VM suspended
        result["step4_suspend_123"] = suspend_vm_on_host(EXTRA_HOST)

        return {
            "message": "UP case 1 executed",
            "details": result,
            "current_states": {
                PROTECTED_HOST: get_vm_state(PROTECTED_HOST),
                STANDBY_HOST: get_vm_state(STANDBY_HOST),
                EXTRA_HOST: get_vm_state(EXTRA_HOST),
            }
        }

    # Cas 2
    if state_122 == "poweredOn" and state_123 == "suspended":
        result = resume_vm_on_host(EXTRA_HOST)
        return {
            "message": "UP case 2 executed",
            "details": result,
            "current_states": {
                PROTECTED_HOST: get_vm_state(PROTECTED_HOST),
                STANDBY_HOST: get_vm_state(STANDBY_HOST),
                EXTRA_HOST: get_vm_state(EXTRA_HOST),
            }
        }

    return {"message": "No action"}


def action_down():
    """
    Cas 1
      124 running
      122 running
      123 running
      => suspend 123

    Cas 2
      124 running
      122 running
      123 suspended
      => destroy 123
      => suspend 122

    Sinon
      no action
    """
    state_124 = get_vm_state(PROTECTED_HOST)
    state_122 = get_vm_state(STANDBY_HOST)
    state_123 = get_vm_state(EXTRA_HOST)

    if state_124 != "poweredOn":
        raise Exception(f"{PROTECTED_HOST} must always be running, current state: {state_124}")

    # Cas 1
    if state_122 == "poweredOn" and state_123 == "poweredOn":
        result = suspend_vm_on_host(EXTRA_HOST)
        return {
            "message": "DOWN case 1 executed",
            "details": result,
            "current_states": {
                PROTECTED_HOST: get_vm_state(PROTECTED_HOST),
                STANDBY_HOST: get_vm_state(STANDBY_HOST),
                EXTRA_HOST: get_vm_state(EXTRA_HOST),
            }
        }

    # Cas 2
    if state_122 == "poweredOn" and state_123 == "suspended":
        result = {}
        result["step1_destroy_123"] = destroy_vm_on_host(EXTRA_HOST)
        result["step2_suspend_122"] = suspend_vm_on_host(STANDBY_HOST)

        return {
            "message": "DOWN case 2 executed",
            "details": result,
            "current_states": {
                PROTECTED_HOST: get_vm_state(PROTECTED_HOST),
                STANDBY_HOST: get_vm_state(STANDBY_HOST),
                EXTRA_HOST: get_vm_state(EXTRA_HOST),
            }
        }

    return {"message": "No action"}


# =========================
# API
# =========================

@app.get("/health")
def health():
    return {"status": "ok", "service": "vm-manager"}


@app.get("/vm/status")
def status():
    try:
        return {
            "vm_name": VM_NAME,
            "protected_host": PROTECTED_HOST,
            "standby_host": STANDBY_HOST,
            "extra_host": EXTRA_HOST,
            "tracked_vms": {
                PROTECTED_HOST: get_vm_info_on_host(PROTECTED_HOST, VM_NAME),
                STANDBY_HOST: get_vm_info_on_host(STANDBY_HOST, VM_NAME),
                EXTRA_HOST: get_vm_info_on_host(EXTRA_HOST, VM_NAME),
            },
            "all_vms_by_host": {
                PROTECTED_HOST: list_host_vms(PROTECTED_HOST),
                STANDBY_HOST: list_host_vms(STANDBY_HOST),
                EXTRA_HOST: list_host_vms(EXTRA_HOST),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vm/up")
def vm_up():
    try:
        return action_up()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vm/down")
def vm_down():
    try:
        return action_down()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
