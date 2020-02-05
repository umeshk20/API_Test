'''
Copyright (C) 2019 Medtronic Diabetes.
All Rights Reserved.
This software is the confidential and proprietary information of
Medtronic Diabetes.  Confidential Information.  You shall not
disclose such Confidential Information and shall use it only in
accordance with the terms of the license agreement you entered into
with Medtronic Diabetes.
'''
import boto3
import traceback
from argparse import ArgumentParser
import os
import sys
import logging
from time import sleep, gmtime, strftime
import time
import yaml
sys.path.append('common_modules/')
sys.path.append('../common_modules/')
sys.path.append('../../common_modules/')
import common_modules

class stackDetails:
    stack_name=''
    TemplateURL=''
    Capabilities=['CAPABILITY_AUTO_EXPAND']
    conf_key=0


def update_template(key,value,source,destination):
    s = open(source).read()
    s = s.replace("$"+key+"$", value)
    f = open(destination, 'w')
    f.write(s)
    f.close()
    
def append_template(key,value,source,destination):
    s = open(source).read()
    s = s.replace("$"+key+"$", value)
    f = open(destination, 'a')
    f.write(s)
    f.close()
    
def delete_variables(source,destination):
    replacer,rn=find_variable_string(source)
    if replacer==0 and rn==0:
        return 0
    s = open(source, 'r+')
    d = open(destination, 'w')
    cnt=0
    for line in s.readlines():
        cnt=cnt+1
        if cnt>=rn-2 and cnt<=rn :
            continue;
        d.write(line)
    d.close()
    s.close()
    return 1
    
def find_variable_string(source):
    f = open(source, 'r+')
    cnt=0
    for line in f.readlines():
        cnt=cnt+1
        if "VAR.KEYS" in line: 
            return line,cnt
    return 0,0  
    
def insert_variables(key,value,source,destination,replacer,rn,cnt):
    if cnt==0:
        s = open(source).read()
        s = s.replace("$VAR.KEYS$", key)
        s = s.replace("$VAR.VALUES$", value)
        f= open(destination, 'w')
        f.write(s)
        f.close()
        return
    f1= open(source, 'r')
    contents=f1.readlines()
    contents.insert(rn,replacer)
    contents = "".join(contents)
    f1.close()
    f= open(destination, 'w')
    f.write(contents)     
    f.close()   
    s = open(source).read()
    s=s.replace("$VAR.KEYS$", key)
    s=s.replace("$VAR.VALUES$", value)
    f= open(destination, 'w')
    f.write(s)       
    f.close()     
  
def deploy_s(args,templateDir):
    logging.info("Reading Config File.")
    stack_list=[]
    s3 = boto3.client('s3')
    
    with open(args.configFilePath) as config_file:  
        data = yaml.load(config_file)
        deploy_cnt=len(data.keys())
        lcnt=1
        while lcnt<=deploy_cnt:
            conf_key = str(lcnt)
            lcnt=lcnt+1
            source=args.BaseTemplate+"/"+data[conf_key]["BaseTemplate"]+"-template.yaml"
            logging.info("Base template used: "+source)
            
            print ("\nFetching configs for : "+conf_key)
            logging.info("\nFetching configs for : "+conf_key)

            if "Deploy" in data[conf_key].keys() :
                if data[conf_key]["Deploy"].upper()=="FALSE" :
                    print( "Deploy=FALSE, Aborting deployment")
                    logging.info("Deploy=FALSE, Aborting deployment")
                    continue
                elif data[conf_key]["Deploy"].upper()!="TRUE" :
                    raise OSError("Unknown value "+data[conf_key]["Deploy"]+" for Parameter Deploy while reading config")
             
            if "Merge" in data[conf_key].keys() :
                template_file=str(data[conf_key]["Merge"])+"-template.yaml"
            else:
                template_file=str(conf_key)+"-template.yaml"
            destination=templateDir+"/"+template_file
            
            if "Variables" not in data[conf_key].keys():
                flag=delete_variables(source,destination)
                if flag!=0:
                    source=destination
            if "Merge" in data[conf_key].keys() :
                append_template("S3Bucket", args.S3BucketJar, source, destination)
            else:
                update_template("S3Bucket", args.S3BucketJar, source, destination)
                stk_name=data[conf_key]["StackName"]
            source=destination
            update_template("FolderName", args.S3FolderJar, source, destination)
            update_template("SubnetId1", args.SubnetID1, source, destination)
            update_template("SubnetId2", args.SubnetID2, source, destination)
            BuildVersion = open(args.VersionReferenceFile).read()
            update_template("Version", BuildVersion, source, destination)
            
            for key in data[conf_key].keys():
                if key == "CheckSumKey":
                    CheckSumKey=data[conf_key][key]
                    ChecksumFile=open(args.checksumFile)
                    chksum_data=yaml.load(ChecksumFile)
                    val=''
                    for ck_key,ck_val in chksum_data.items():
                        if CheckSumKey in ck_key:
                            val=ck_val
                            break
                    logging.info(key+" = "+val)
                    update_template(key, val, source, destination)
                elif key!="Variables":
                    val=data[conf_key][key]
                    logging.info(key+" = "+val)
                    update_template(key, val, source, destination)
                elif key=="Variables":
                    logging.info( key+":")
                    replacer,rn=find_variable_string(source)
                    cnt=0
                    for k,v in data[conf_key][key].items():
                        insert_variables(k,v,source,destination,replacer,rn,cnt)
                        cnt=cnt+1
                        logging.info( "\t"+k+": "+v)
                    

            print ("Template processed for : "+data[conf_key]["DisplayName"])
            logging.info("Template processed for : "+conf_key)
            
            
            if args.TemplateFolder=="":
                s3.upload_file(destination,args.TemplateBKT,template_file)
                template_url = '%s/%s/%s' % (s3.meta.endpoint_url, args.TemplateBKT, template_file)
            else :
                s3.upload_file(destination,args.TemplateBKT,args.TemplateFolder+"/"+template_file)
                template_url = '%s/%s/%s' % (s3.meta.endpoint_url, args.TemplateBKT,args.TemplateFolder+"/"+template_file)
                
            logging.info("Name= "+conf_key+" Template URL= "+template_url)

            obj=stackDetails()

            if "Merge" not in data[conf_key].keys():
                obj.stack_name=stk_name
                obj.TemplateURL=template_url
                obj.conf_key=conf_key
                stack_list.append(obj)


    return stack_list
if __name__ == '__main__':
    
    parser = ArgumentParser()
    parser.add_argument("--templateBucket", dest="TemplateBKT", required=True, metavar="<TemplateBKT>",
                        help="S3 Bucket name to store templates")
    parser.add_argument("--templateFolder", dest="TemplateFolder", required=False, metavar="<TemplateFolder>",default="",
                        help="Folder name in s3 bucket to store templates")
    parser.add_argument("--subnetID1", dest="SubnetID1", required=True, metavar="<SubnetID1>",
                        help="Subnet ID 1")
    parser.add_argument("--subnetID2", dest="SubnetID2", required=True, metavar="<SubnetID2>",
                        help="Subnet ID 2")
    parser.add_argument("--versionReferenceFile", dest="VersionReferenceFile", required=True, metavar="<VersionReferenceFile>",
                        help="Path of Build Version Reference File")
    parser.add_argument("--checksumFile", dest="checksumFile", required=True, metavar="<checksumFile>",
                        help="Checksum File")
    parser.add_argument("--s3BucketJar", dest="S3BucketJar", required=True, metavar="<S3BucketJar>",
                        help="S3 bucket for  JARs")
    parser.add_argument("--s3FolderJar", dest="S3FolderJar", required=False, metavar="<S3FolderJar>",default="",
                        help="S3 Folder for  JARs")
    parser.add_argument("--configFilePath", dest="configFilePath", required=True, metavar="<configFilePath>",
                        help="Config file path")
    parser.add_argument("--baseTemplatePath", dest="BaseTemplate", required=True, metavar="<BaseTemplate>",
                        help="Base Template folder path in local directory")
    parser.add_argument("--logLevel", dest="logLevel", required=False, metavar="<logLevel>",default="INFO",
                       help="Logging level INFO|DEBUG|ERROR|WARNING")
    args = parser.parse_args()
    
    logDir = os.getcwd() + "/log"
    if not os.path.exists(logDir):
        os.makedirs(logDir)
        
    templateDir=os.getcwd() + "/temp"
    if not os.path.exists(templateDir):
        os.makedirs(templateDir)
    else:
        for fname in os.listdir(os.getcwd() + "/temp"):
            os.remove(os.getcwd() + "/temp/"+fname)
            
    try: 
        
        logFile = logDir +  '/'+os.path.splitext(os.path.basename(__file__))[0] + strftime("%Y%m%d%H%M", gmtime()) + '.log'
        logging.basicConfig(filename=logFile, filemode='w', level=args.logLevel, format='%(asctime)s   %(levelname)s     %(message)s')
        
        stack_list=deploy_s(args,templateDir)
        cloudformation = boto3.resource('cloudformation')
        for stack in stack_list:
            print("\nDeploying: "+stack.conf_key)
            print("\nStack Name: "+stack.stack_name+" template_URL: "+stack.TemplateURL+" Capabilities: "+str(stack.Capabilities))
            cloudformation.create_stack(StackName=stack.stack_name,TemplateURL=stack.TemplateURL,Capabilities=stack.Capabilities)
            common_modules.get_stack_status(cloudformation, stack.stack_name)
            print( "Stack "+stack.stack_name+" deployed successfully...")
            logging.info("\nStack "+stack.stack_name+" deployed successfully...")
                    
    except Exception as exp:
        logging.error("Caught Exception %s", str(exp))
        print("Error occured.")
        traceback.print_exc("Caught Exception %s", str(exp))
        raise OSError("Caught Exception %s", str(exp))
        sys.exit()
