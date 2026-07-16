@echo off
echo Generating proto files...
cd D:\Projects\dcap-system
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/dcap/manager.proto
echo Done!
pause