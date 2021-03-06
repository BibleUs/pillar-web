import json
import os
from datetime import datetime

from pillarsdk import Node
from pillarsdk import NodeType
from pillarsdk import User
from pillarsdk import File
# from pillarsdk import binaryFile
from pillarsdk.exceptions import ResourceNotFound
from pillarsdk.exceptions import ForbiddenAccess

from flask import abort
from flask import Blueprint
from flask import render_template
from flask import redirect
from flask import url_for
from flask import request
from flask import jsonify
from flask import session
from wtforms import SelectMultipleField

from application.modules.nodes.forms import get_node_form
from application.modules.nodes.forms import get_comment_form
from application.modules.nodes.forms import process_node_form
from application.modules.nodes.custom.storage import StorageNode
from application.helpers import Pagination

from application import app
from application import SystemUtility

from flask.ext.login import login_required
from flask.ext.login import current_user

from jinja2.exceptions import TemplateNotFound

RFC1123_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'

nodes = Blueprint('nodes', __name__)

def type_names():
    api = SystemUtility.attract_api()

    types = NodeType.all(api=api)['_items']
    type_names = []
    for names in types:
        type_names.append(str(names['name']))
    return type_names


def assigned_users_to(node, node_type):
    api = SystemUtility.attract_api()

    if node_type['name'] != "task":
        return []
    users = node['properties']['owners']['users']
    owners = []
    for user in users:
        user_node = User.find(user, api=api)
        owners.append(user_node)
    return owners


@nodes.route("/<node_type_name>")
def index(node_type_name=""):
    """Generic function to list all nodes
    """
    # Pagination index
    page = request.args.get('page', 1)
    max_results = 50

    api = SystemUtility.attract_api()
    if node_type_name == "":
        node_type_name = "shot"

    node_type = NodeType.find_first({
        'where': '{"name" : "%s"}' % node_type_name,
        }, api=api)

    if not node_type:
        return "Empty NodeType list", 200

    nodes = Node.all({
        'where': '{"node_type" : "%s"}' % (node_type._id),
        'max_results': max_results,
        'page': page,
        'embedded': '{"picture":1}',
        'sort' : "order"}, api=api)

    # Build the pagination object
    pagination = Pagination(int(page), max_results, nodes._meta.total)

    template = '{0}/index.html'.format(node_type_name)
    try:
        return render_template(
            template,
            title=node_type_name,
            nodes=nodes,
            node_type=node_type,
            type_names=type_names(),
            pagination=pagination)
    except TemplateNotFound:
        return render_template(
            'nodes/index.html',
            title=node_type_name,
            nodes=nodes,
            node_type=node_type,
            type_names=type_names(),
            pagination=pagination)


@nodes.route("/<node_type_id>/add", methods=['GET', 'POST'])
@login_required
def add(node_type_id):
    """Generic function to add a node of any type
    """
    api = SystemUtility.attract_api()
    ntype = NodeType.find(node_type_id, api=api)
    form = get_node_form(ntype)
    user_id = current_user.objectid
    if form.validate_on_submit():
        if process_node_form(form, node_type=ntype, user=user_id):
            return redirect(url_for('nodes.index', node_type_name=ntype['name']))
    else:
        print form.errors
    return render_template('nodes/add.html',
        node_type=ntype,
        form=form,
        errors=form.errors,
        type_names=type_names())


def jstree_parse_node(node, children=None):
    """Generate JStree node from node object"""
    node_type = node.node_type.name
    if node_type == 'asset':
        node_type = node.properties.content_type
    return dict(
        id="n_{0}".format(node._id),
        text=node.name,
        type=node_type,
        children=True)


def jstree_get_children(node_id):
    api = SystemUtility.attract_api()
    children_list = []

    if node_id.startswith('n_'):
        node_id = node_id.split('_')[1]
    try:
        children = Node.all({
            'projection': '{"name": 1, "parent": 1, "node_type": 1, "properties": 1}',
            'embedded': '{"node_type": 1}',
            'where': '{"parent": "%s"}' % node_id}, api=api)
        for child in children._items:
            # Skip nodes of type comment
            if child.node_type.name != 'comment':
                children_list.append(jstree_parse_node(child))
    except ForbiddenAccess:
        pass

    return children_list


def jstree_build_children(node):
    return dict(
        id="n_{0}".format(node._id),
        text=node.name,
        type=node.node_type.name,
        children=jstree_get_children(node._id)
    )


def jstree_build_from_node(node):
    api = SystemUtility.attract_api()
    open_nodes = [jstree_parse_node(node)]
    # Get the current node again (with parent data)
    try:
        parent = Node.find(node.parent, {
            'projection': '{"name": 1, "parent": 1, "node_type": 1}',
            'embedded': '{"node_type":1}',
            }, api=api)
    except ResourceNotFound:
        parent = None
    except ForbiddenAccess:
        parent = None
    while (parent):
        open_nodes.append(jstree_parse_node(parent))
        # If we have a parent
        if parent.parent:
            try:
                parent = Node.find(parent.parent, {
                    'projection': '{"name":1, "parent":1, "node_type": 1}',
                    'embedded': '{"node_type":1}',
                    }, api=api)
            except ResourceNotFound:
                parent = None
        else:
            parent = None
    open_nodes.reverse()
    #open_nodes.pop(0)

    nodes_list = []

    for node in jstree_get_children(open_nodes[0]['id']):
        # Nodes at the root of the project
        node_dict = {
            'id': node['id'],
            'text': node['text'],
            'type': node['type'],
            'children': True
        }
        if len(open_nodes) > 1:
            # Opening and selecting the tree nodes according to the landing place
            if node['id'] == open_nodes[1]['id']:
                current_dict = node_dict
                current_dict['state'] = {'opened': True}
                current_dict['children'] = jstree_get_children(node['id'])
                # Iterate on open_nodes until the end
                for n in open_nodes[2:]:
                    for c in current_dict['children']:
                        if n['id'] == c['id']:
                            current_dict = c
                            break
                    current_dict['state'] = {'opened': True}
                    current_dict['children'] = jstree_get_children(n['id'])

                # if landing_asset_id:
                #     current_dict['children'] = aux_product_tree_node(open_nodes[-1])
                #     for asset in current_dict['children']:
                #         if int(asset['id'][1:])==landing_asset_id:
                #             asset.update(state=dict(selected=True))

        nodes_list.append(node_dict)
    return nodes_list


class FakeUser(object):
    def __init__(self):
        super(FakeUser, self).__init__()
        self.full_name = 'Anonymous user'


class FakeNodeAsset(Node):
    def __init__(self):
        super(FakeNodeAsset, self).__init__()
        self.name = 'Asset'
        self.description = 'Login to view this asset'
        self.user = FakeUser()
        self.properties = None

@nodes.route("/<node_id>/view")
def view(node_id):
    #import time
    #start = time.time()
    api = SystemUtility.attract_api()
    # Get node with embedded picture data
    try:
        node = Node.find(node_id + '/?embedded={"picture":1, "node_type":1}', api=api)
    except ResourceNotFound:
        return abort(404)
    except ForbiddenAccess:
        return abort(403)

    node_type_name = node.node_type.name

    # JsTree functionality.
    # This return a lightweight version of the node, to be used by JsTree in the
    # frontend. We have two possible cases:
    # - https://pillar/<node_id>/view?format=jstree (construct the whole expanded
    #   tree starting from the node_id. Use only once)
    # - https://pillar/<node_id>/view?format=jstree&children=1 (deliver the
    #   children of a node - use in the navigation of the tree)

    if request.args.get('format') and request.args.get('format') == 'jstree':
        if request.args.get('children') == '1':
            if node_type_name == 'storage':
                storage = StorageNode(node)
                # Check if we specify a path within the storage
                path = request.args.get('path')
                # Generate the storage listing
                listing = storage.browse(path)
                # Inject the current node id in the response, so that JsTree can
                # expose the storage_node property and use it for further queries
                listing['storage_node'] = node._id
                if 'children' in listing:
                    for child in listing['children']:
                        child['storage_node'] = node._id
                return jsonify(listing)
            else:
                return jsonify(jstree_build_children(node))
        else:
            return jsonify(items=jstree_build_from_node(node))
    # Continue to process the node (for HTML, HTML embeded and JSON responses)

    # Set the default name of the template path based on the node name
    template_path = os.path.join('nodes', 'custom', node_type_name)
    # Set the default action for a template. By default is view and we override
    # it only if we are working storage nodes, where an 'index' is also possible
    template_action = 'view'

    # XXX Code to detect a node of type asset, and aggregate file data
    if node_type_name == 'asset':
        node_file = File.find(node.properties.file, api=api)
        node_file_children = node_file.children(api=api)
        # Attach the file node to the asset node
        setattr(node, 'file', node_file)

        try:
            asset_type = node_file.content_type.split('/')[0]
        except AttributeError:
            asset_type = None

        if asset_type == 'video':
            # Process video type and select video template
            sources = []
            if node_file_children:
                for f in node_file_children._items:
                    sources.append(dict(
                        type=f.content_type,
                        src=f.link))

            setattr(node, 'video_sources', json.dumps(sources))
            setattr(node, 'file_children', node_file_children)
            template_path = os.path.join(template_path, asset_type)
        elif asset_type == 'image':
            # Process image type and select image template
            #setattr(node, 'file_children', node_file_children)
            template_path = os.path.join(template_path, asset_type)
        else:
            # Treat it as normal file (zip, blend, application, etc)
            template_path = os.path.join(template_path, 'file')
    # XXX The node is of type project
    elif node_type_name == 'project':
        if node.properties.picture_square:
            picture_square = File.find(node.properties.picture_square, api=api)
            node.properties.picture_square = picture_square
        if node.properties.picture_header:
            picture_header = File.find(node.properties.picture_header, api=api)
            node.properties.picture_header = picture_header
        if node.properties.nodes_latest:
            list_latest = []
            for node_id in node.properties.nodes_latest:
                try:
                    node_item = Node.find(node_id, {
                        'projection': '{"name":1, "user":1, "node_type":1}',
                        'embedded': '{"user":1}',
                        }, api=api)
                    list_latest.append(node_item)
                except ForbiddenAccess:
                    list_latest.append(FakeNodeAsset())
            node.properties.nodes_latest = list(reversed(list_latest))
        if node.properties.nodes_featured:
            list_featured = []
            for node_id in node.properties.nodes_featured:
                try:
                    node_item = Node.find(node_id, {
                        'projection': '{"name":1, "user":1, "picture":1, "node_type":1}',
                        'embedded': '{"user":1}',
                        }, api=api)
                    picture = File.find(node_item.picture, api=api)
                    node_item.picture = picture
                    list_featured.append(node_item)
                except ForbiddenAccess:
                    list_featured.append(FakeNodeAsset())
            node.properties.nodes_featured = list(reversed(list_featured))

    elif node_type_name == 'storage':
        storage = StorageNode(node)
        path = request.args.get('path')
        listing = storage.browse(path)
        node.name = listing['name']
        listing['storage_node'] = node._id
        # If the item has children we are working with a group
        if 'children' in listing:
            for child in listing['children']:
                child['storage_node'] = node._id
                child['name'] = child['text']
                child['content_type'] = os.path.dirname(child['type'])
            node.children = listing['children']
            template_action = 'index'
        else:
            node.status = 'published'
            node.length = listing['size']
            node.download_link = listing['signed_url']

    # Get previews
    if node.picture:
        node.picture = File.find(node.picture._id, api=api)
    # Get Parent
    try:
        parent = Node.find(node['parent'], api=api)
    except KeyError:
        parent = None
    except ResourceNotFound:
        parent = None
    # Get children
    try:
        children = Node.all({
            'where': '{"parent": "%s"}' % node._id,
            'embedded': '{"picture": 1, "node_type": 1}'}, api=api)
        children = children._items
    except ForbiddenAccess:
        return abort(403)

    for child in children:
        if child.picture:
            child.picture = File.find(child.picture._id, api=api)

    if request.args.get('format'):
        if request.args.get('format') == 'json':
            node = node.to_dict()
            node['url_edit'] = url_for('nodes.edit', node_id=node['_id']),
            if parent:
                parent = parent.to_dict()
            return_content = jsonify({
                'node': node,
                'children': children.to_dict(),
                'parent': parent
            })
    else:
        embed_string = ''
        # Check if we want to embed the content via an AJAX call
        if request.args.get('embed'):
            if request.args.get('embed') == '1':
                # Define the prefix for the embedded template
                embed_string = '_embed'

        # Check if template exists on the filesystem
        template_path = '{0}/{1}{2}.html'.format(template_path,
                                                template_action, embed_string)
        template_path_full = os.path.join(app.config['TEMPLATES_PATH'],
                                        template_path)
        if not os.path.exists(template_path_full):
            return "Missing template"

        return_content = render_template(template_path,
            node=node,
            type_names=type_names(),
            parent=parent,
            children=children,
            config=app.config)

    #print(time.time() - start)
    return return_content


def project_update_nodes_list(node_id, project_id=None, list_name='latest'):
    """Update the project node with the latest edited or favorited node.
    The list value can be 'latest' or 'featured' and it will determined where
    the node reference will be placed in.
    """
    if not project_id and 'current_project_id' in session:
        project_id = session['current_project_id']
    elif not project_id:
        return None
    api = SystemUtility.attract_api()
    project = Node.find(project_id, api=api)
    if list_name == 'latest':
        nodes_list = project.properties.nodes_latest
    else:
        nodes_list = project.properties.nodes_featured

    # Do not allow adding project to lists
    if node_id == project._id:
        return "fail"

    if not nodes_list:
        node_list_name = 'nodes_' + list_name
        project.properties[node_list_name] = []
        nodes_list = project.properties[node_list_name]
    elif len(nodes_list) > 5:
        nodes_list.pop(0)

    if node_id in nodes_list:
        # Pop to put this back on top of the list
        nodes_list.remove(node_id)
        if list_name == 'featured':
            # We treat the action as a toggle and do not att the item back
            project.update(api=api)
            return "removed"

    nodes_list.append(node_id)
    project.update(api=api)
    return "added"


@nodes.route("/<node_id>/edit", methods=['GET', 'POST'])
@login_required
def edit(node_id):
    """Generic node editing form
    """
    def set_properties(
            dyn_schema, form_schema, node_properties, form, prefix="", set_data=True):
        """Initialize custom properties for the form. We run this function once
        before validating the function with set_data=False, so that we can set
        any multiselect field that was originally specified empty and fill it
        with the current choices.
        """
        for prop in dyn_schema:
            if not prop in node_properties:
                continue
            schema_prop = dyn_schema[prop]
            form_prop = form_schema[prop]
            prop_name = "{0}{1}".format(prefix, prop)
            if schema_prop['type'] == 'dict':
                set_properties(
                    schema_prop['schema'],
                    form_prop['schema'],
                    node_properties[prop_name],
                    form,
                    "{0}__".format(prop_name))
            else:
                try:
                    data = node_properties[prop]
                except KeyError:
                    print ("{0} not found in form".format(prop_name))
                if schema_prop['type'] == 'datetime':
                    data = datetime.strptime(data, RFC1123_DATE_FORMAT)
                if prop_name in form:
                    # Other field types
                    if isinstance(form[prop_name], SelectMultipleField):
                        # If we are dealing with a multiselect field, check if
                        # it's empty (usually because we can't query the whole
                        # database to pick all the choices). If it's empty we
                        # populate the choices with the actual data.
                        if not form[prop_name].choices:
                            form[prop_name].choices = [(d,d) for d in data]
                            # Choices should be a tuple with value and name
                    # Assign data to the field
                    if set_data:
                        form[prop_name].data = data

    api = SystemUtility.attract_api()
    node = Node.find(node_id, api=api)
    # TODO: simply embed node_type
    node_type = NodeType.find(node.node_type, api=api)
    form = get_node_form(node_type)
    user_id = current_user.objectid
    dyn_schema = node_type['dyn_schema'].to_dict()
    form_schema = node_type['form_schema'].to_dict()
    error = ""
    node_type_name = node_type.name

    node_properties = node.properties.to_dict()

    set_properties(dyn_schema, form_schema, node_properties, form, set_data=False)

    if form.validate_on_submit():
        if process_node_form(
                form, node_id=node_id, node_type=node_type, user=user_id):
            project_update_nodes_list(node_id)
            return redirect(url_for('nodes.view', node_id=node_id, embed=1))
        else:
            error = "Server error"
            print ("Error sending data")
    else:
        print form.errors

    # Populate Form
    form.name.data = node.name
    form.description.data = node.description
    if 'picture' in form:
        form.picture.data = node.picture
    if node.parent:
        form.parent.data = node.parent

    set_properties(dyn_schema, form_schema, node_properties, form)

    # Get Parent
    try:
        parent = Node.find(node['parent'], api=api)
    except KeyError:
        parent = None
    except ResourceNotFound:
        parent = None

    embed_string = ''
    # Check if we want to embed the content via an AJAX call
    if request.args.get('embed'):
        if request.args.get('embed') == '1':
            # Define the prefix for the embedded template
            embed_string = '_embed'

    template = '{0}/edit{1}.html'.format(node_type['name'], embed_string)

    # We should more simply check if the template file actually exsists on
    # the filesystem level
    try:
        return render_template(
                template,
                node=node,
                parent=parent,
                form=form,
                errors=form.errors,
                error=error)
    except TemplateNotFound:
        template = 'nodes/edit{1}.html'.format(node_type['name'], embed_string)
        return render_template(
                template,
                node=node,
                parent=parent,
                form=form,
                errors=form.errors,
                error=error)


@nodes.route("/<node_id>/delete", methods=['GET', 'POST'])
@login_required
def delete(node_id):
    """Generic node deletion
    """
    api = SystemUtility.attract_api()
    node = Node.find(node_id, api=api)
    name = node.name
    node_type = NodeType.find(node.node_type, api=api)
    try:
        node.delete(api=api)
        forbidden = False
    except ForbiddenAccess:
        forbidden = True

    if not forbidden:
        # print (node_type['name'])
        return redirect(url_for('nodes.index', node_type_name=node_type['name']))
    else:
        return redirect(url_for('nodes.edit', node_id=node._id))


# Import of custom modules (using the same nodes decorator)
from application.modules.nodes.custom.assets import *
