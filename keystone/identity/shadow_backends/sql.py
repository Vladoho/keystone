# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import uuid

from keystone.common import sql
from keystone import exception
from keystone.identity.backends import base as identity_base
from keystone.identity.backends import sql_model as model
from keystone.identity.shadow_backends import base


class ShadowUsers(base.ShadowUsersDriverV10):
    @sql.handle_conflicts(conflict_type='federated_user')
    def create_federated_user(self, federated_dict):
        user = {
            'id': uuid.uuid4().hex,
            'enabled': True
        }
        with sql.session_for_write() as session:
            federated_ref = model.FederatedUser.from_dict(federated_dict)
            user_ref = model.User.from_dict(user)
            user_ref.federated_users.append(federated_ref)
            session.add(user_ref)
            return identity_base.filter_user(user_ref.to_dict())

    def get_federated_user(self, idp_id, protocol_id, unique_id):
        user_ref = self._get_federated_user(idp_id, protocol_id, unique_id)
        return identity_base.filter_user(user_ref.to_dict())

    def _get_federated_user(self, idp_id, protocol_id, unique_id):
        """Return the found user for the federated identity.

        :param idp_id: The identity provider ID
        :param protocol_id: The federation protocol ID
        :param unique_id: The user's unique ID (unique within the IdP)
        :returns User: Returns a reference to the User

        """
        with sql.session_for_read() as session:
            query = session.query(model.User).outerjoin(model.LocalUser)
            query = query.join(model.FederatedUser)
            query = query.filter(model.FederatedUser.idp_id == idp_id)
            query = query.filter(model.FederatedUser.protocol_id ==
                                 protocol_id)
            query = query.filter(model.FederatedUser.unique_id == unique_id)
            try:
                user_ref = query.one()
            except sql.NotFound:
                raise exception.UserNotFound(user_id=unique_id)
            return user_ref

    @sql.handle_conflicts(conflict_type='federated_user')
    def update_federated_user_display_name(self, idp_id, protocol_id,
                                           unique_id, display_name):
        with sql.session_for_write() as session:
            query = session.query(model.FederatedUser)
            query = query.filter(model.FederatedUser.idp_id == idp_id)
            query = query.filter(model.FederatedUser.protocol_id ==
                                 protocol_id)
            query = query.filter(model.FederatedUser.unique_id == unique_id)
            query = query.filter(model.FederatedUser.display_name !=
                                 display_name)
            query.update({'display_name': display_name})
            return

    @sql.handle_conflicts(conflict_type='nonlocal_user')
    def create_nonlocal_user(self, user_dict):
        new_user_dict = copy.deepcopy(user_dict)
        new_nonlocal_user_dict = {
            'domain_id': user_dict['domain_id'],
            'name': user_dict['name']
        }
        with sql.session_for_write() as session:
            new_nonlocal_user_ref = model.NonLocalUser.from_dict(
                new_nonlocal_user_dict)
            new_user_ref = model.User.from_dict(new_user_dict)
            new_user_ref.nonlocal_users.append(new_nonlocal_user_ref)
            session.add(new_user_ref)
            return identity_base.filter_user(new_user_ref.to_dict())

    def get_user(self, user_id):
        with sql.session_for_read() as session:
            user_ref = self._get_user(session, user_id)
            return identity_base.filter_user(user_ref.to_dict())

    def _get_user(self, session, user_id):
        user_ref = session.query(model.User).get(user_id)
        if not user_ref:
            raise exception.UserNotFound(user_id=user_id)
        return user_ref
