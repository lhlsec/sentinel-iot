import React from "react";
import {Card, CardBody, CardHeader, CardFooter, Modal, ModalBody, ModalFooter, ModalHeader, Button, Alert} from "reactstrap";
import {OutValue} from "./outValue";
import PropTypes from "prop-types";

export class Datastore extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            showDeleteModal: false,
            date: new Date(Date.now()).toLocaleTimeString()
        };
        this.toggleDeleteModal = this.toggleDeleteModal.bind(this);
        this.updateTime = this.updateTime.bind(this);
        this.send = this.send.bind(this);
    }

    toggleDeleteModal() {
        this.setState((prev, props) => {return {showDeleteModal: !prev.showDeleteModal};});
    }

    updateTime() {
        this.setState({date: new Date(Date.now()).toLocaleTimeString()});
    }

    componentDidUpdate(prevProps, prevState) {
        if(prevProps.value !== this.props.value) {
            this.updateTime();
        }
    }

    send(value) {
        let headers = Object.assign({}, window.putHeader);
        headers.body = JSON.stringify({value: value, format: this.props.format});
        fetch(window.host + "/api/hub/" + window.hub + "/datastores/" + this.props.name, headers)
            .then(r => {
                if(r.ok) {
                    r.json().then(json => {
                            if (!json.accepted) {
                                console.log("Error: " + json.reason);
                            }
                        }
                    ).catch(() => console.log("Error: error occured parsing response"))
                } else {
                    r.text().then(text => console.log(text));
                    console.log("Error: " + r.statusText + " (" + r.status + ")");
                }
            })
            .catch((e) => console.log("Error: an unknown error has occured\n"+e));
    }

    render(){
       return (
                <div className="leaf col-sm-12 col-md-6 col-lg-4 col-xl-4">
                    <Card>
                      <CardHeader>
                          <div className="float-left grabber leaf-icon drag-handle"><i className="fas fa-bars" /></div>
                          <div className="float-left">{this.props.name}</div>
                          <div className="float-right" id="datastore" data-toggle="dropdown" aria-haspopup="true" aria-expanded="false">
                            <div className="dropdown-toggle dropdown-toggle-split pointer leaf-icon"></div>
                          </div>
                          <div className="dropdown-menu" aria-labelledby="leafdropdown">
                              <button className="dropdown-item" onClick={this.toggleDeleteModal}>Delete Datastore</button>
                          </div>
                          <Modal isOpen={this.state.showDeleteModal} toggle={this.toggleDeleteModal}>
                          <ModalHeader toggle={this.toggleDeleteModal}>{"Delete Datastore: " + this.props.name}</ModalHeader>
                          <ModalBody>
                            <p>Are you sure you want to delete this datastore?</p>
                          </ModalBody>
                          <ModalFooter>
                            <Button color="danger" onClick={() => this.props.delete(this)}>Yes</Button>{' '}
                            <Button color="secondary" onClick={this.toggleDeleteModal}>No</Button>
                          </ModalFooter>
                        </Modal>
                      </CardHeader>
                      <CardBody>
                        <div className="row">
                            <div className="col-md-6"><strong>Format</strong></div>
                            <div className="col-md-6"><strong>Value</strong></div>
                        </div>
                        <div className="row">
                            <div className="col-md-6">{this.props.format}</div>
                            <div className="col-md-6"><OutValue send={this.send} format={this.props.format} value={this.props.value} small connected/></div>
                        </div>
                      </CardBody>
                      <CardFooter className="text-muted text-center">
                          Last Updated: { this.state.date }
                      </CardFooter>
                    </Card>
                </div>);
    }
}

Datastore.propTypes = {
    name: PropTypes.string,
    format: PropTypes.string,
    value: PropTypes.any,
    update: PropTypes.func,
    delete: PropTypes.func
};